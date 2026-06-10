import { type FormEvent, type PointerEvent, useEffect, useMemo, useRef, useState } from "react";
import type {
  CareContext,
  CarePlan,
  ChatMessage,
  Observation,
  PetDetail,
  PetSummary,
  UserAccount,
  UserResponse,
  View,
} from "./types";

const workspaceStorageKey = "pawcareWorkspaceV1";
const chatStoragePrefix = "pawcareChatHistoryV1";

const dogBreeds = [
  ["", "Unknown / mixed"],
  ["Border Collie", "Border Collie"],
  ["Golden Retriever", "Golden Retriever"],
  ["Labrador Retriever", "Labrador Retriever"],
  ["Poodle", "Poodle"],
  ["French Bulldog", "French Bulldog"],
  ["German Shepherd", "German Shepherd"],
  ["Corgi", "Corgi"],
  ["Dachshund", "Dachshund"],
  ["Shiba Inu", "Shiba Inu"],
  ["Other", "Other"],
];

const catBreeds = [
  ["", "Unknown / mixed"],
  ["Domestic Shorthair", "Domestic Shorthair"],
  ["Domestic Longhair", "Domestic Longhair"],
  ["British Shorthair", "British Shorthair"],
  ["American Shorthair", "American Shorthair"],
  ["Ragdoll", "Ragdoll"],
  ["Siamese", "Siamese"],
  ["Maine Coon", "Maine Coon"],
  ["Persian", "Persian"],
  ["Sphynx", "Sphynx"],
  ["Other", "Other"],
];

const ageOptions = [
  ["", "Unknown"],
  ["0.08", "1 month"],
  ["0.17", "2 months"],
  ["0.25", "3 months"],
  ["0.33", "4 months"],
  ["0.42", "5 months"],
  ["0.5", "6 months"],
  ["0.58", "7 months"],
  ["0.67", "8 months"],
  ["0.75", "9 months"],
  ["0.83", "10 months"],
  ["0.92", "11 months"],
  ["1", "12 months"],
  ["1.3", "1.3 years"],
  ["1.6", "1.6 years"],
  ["1.8", "1.8 years"],
  ["2", "2 years"],
  ["3", "3 years"],
  ["4", "4 years"],
  ["5", "5 years"],
  ["6", "6 years"],
  ["7", "7 years"],
  ["8", "8 years"],
  ["9", "9 years"],
  ["10", "10 years"],
  ["11", "11 years"],
  ["12", "12 years"],
  ["13", "13+ years"],
];

type PetFormState = {
  name: string;
  species: string;
  avatar: string;
  avatarImage: string;
  avatarZoom: string;
  avatarX: string;
  avatarY: string;
  breed: string;
  ageYears: string;
  weightKg: string;
  normalAppetite: string;
  normalStool: string;
  normalActivity: string;
  medicalNotes: string;
};

const blankPetForm: PetFormState = {
  name: "",
  species: "dog",
  avatar: "collie",
  avatarImage: "",
  avatarZoom: "1",
  avatarX: "50",
  avatarY: "50",
  breed: "",
  ageYears: "",
  weightKg: "",
  normalAppetite: "unknown",
  normalStool: "unknown",
  normalActivity: "unknown",
  medicalNotes: "",
};

export function PawCareApp() {
  const [userId, setUserId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [pets, setPets] = useState<PetSummary[]>([]);
  const [selectedPetId, setSelectedPetId] = useState("");
  const [selectedPetDetail, setSelectedPetDetail] = useState<PetDetail | null>(null);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [view, setView] = useState<View>("home");
  const [notice, setNotice] = useState("");
  const [petFormOpen, setPetFormOpen] = useState(false);
  const [petFormMode, setPetFormMode] = useState<"create" | "edit">("create");
  const [petForm, setPetForm] = useState<PetFormState>(blankPetForm);
  const [rawText, setRawText] = useState("");
  const [observationCategory, setObservationCategory] = useState("appetite");
  const [observationDetails, setObservationDetails] = useState("");
  const [observationSeverity, setObservationSeverity] = useState("mild");
  const [duplicateWarning, setDuplicateWarning] = useState("");
  const [pendingDuplicateMeal, setPendingDuplicateMeal] = useState("");
  const [chatByPetId, setChatByPetId] = useState<Record<string, ChatMessage[]>>({});
  const [carePlanByPetId, setCarePlanByPetId] = useState<Record<string, CarePlan>>({});
  const [carePlanEditing, setCarePlanEditing] = useState(false);
  const [careDraft, setCareDraft] = useState<CarePlan>(defaultCarePlan());
  const [isSending, setIsSending] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const chatHydratedUserRef = useRef("");

  const selectedPet = pets.find((pet) => pet.pet_id === selectedPetId) || null;
  const currentChat = chatByPetId[selectedPetId || "_system"] || [
    assistantGreeting(selectedPet),
  ];
  const totalObservations = pets.reduce((total, pet) => total + pet.observation_count, 0);
  const alertCount = observations.filter((observation) =>
    ["vomiting", "stool", "medication_note", "mobility", "urination"].includes(
      observation.category,
    ),
  ).length;

  useEffect(() => {
    const saved = restoreSession();
    if (!saved?.user_id) return;
    setUserId(saved.user_id);
    setDisplayName(saved.display_name || "there");
    setSelectedPetId(saved.selected_pet_id || "");
  }, []);

  useEffect(() => {
    if (!userId) return;
    saveSession({
      user_id: userId,
      display_name: displayName,
      selected_pet_id: selectedPetId,
    });
  }, [userId, displayName, selectedPetId]);

  useEffect(() => {
    if (!userId || chatHydratedUserRef.current === userId) return;
    setChatByPetId(restoreChatHistory(userId));
    chatHydratedUserRef.current = userId;
  }, [userId]);

  useEffect(() => {
    if (!userId || chatHydratedUserRef.current !== userId) return;
    saveChatHistory(userId, chatByPetId);
  }, [userId, chatByPetId]);

  useEffect(() => {
    if (!userId) return;
    void loadPets(userId, selectedPetId);
  }, [userId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ block: "end" });
  }, [currentChat.length, currentChat[currentChat.length - 1]?.message]);

  async function loadPets(currentUserId = userId, preferredPetId = selectedPetId) {
    const result = await api<{ pets: PetSummary[] }>(
      `/v1/users/${encodeURIComponent(currentUserId)}/pets`,
    );
    setPets(result.pets);
    const nextPetId =
      preferredPetId && result.pets.some((pet) => pet.pet_id === preferredPetId)
        ? preferredPetId
        : result.pets[0]?.pet_id || "";
    setSelectedPetId(nextPetId);
    if (nextPetId) {
      await selectPet(nextPetId, currentUserId);
    } else {
      setSelectedPetDetail(null);
      setObservations([]);
    }
  }

  async function selectPet(petId: string, currentUserId = userId) {
    setSelectedPetId(petId);
    setView("home");
    ensureChatForPet(petId, pets.find((pet) => pet.pet_id === petId) || null);
    const detail = await api<PetDetail>(
      `/v1/users/${encodeURIComponent(currentUserId)}/pets/${encodeURIComponent(petId)}`,
    );
    setSelectedPetDetail(detail);
    const result = await api<{ observations: Observation[] }>(
      `/v1/users/${encodeURIComponent(currentUserId)}/pets/${encodeURIComponent(
        petId,
      )}/observations`,
    );
    setObservations(result.observations);
  }

  async function handleWorkspaceSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!displayName.trim() || !email.trim()) {
      setNotice("Name and email are required.");
      return;
    }
    const user = await api<UserAccount>("/v1/users", {
      method: "POST",
      body: { display_name: displayName.trim(), email: email.trim() },
    });
    setUserId(user.user_id);
    setDisplayName(user.display_name || user.email || "there");
    setSelectedPetId("");
    setSelectedPetDetail(null);
    setObservations([]);
    setChatByPetId(restoreChatHistory(user.user_id));
    chatHydratedUserRef.current = user.user_id;
    setCarePlanByPetId({});
    await loadPets(user.user_id, "");
  }

  async function handlePetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!userId) {
      setNotice("Enter a user workspace first.");
      return;
    }
    if (!petForm.name.trim()) {
      setNotice("Pet name is required.");
      return;
    }
    const targetPetId =
      petFormMode === "edit" && selectedPetId
        ? selectedPetId
        : generatePetId(petForm.name, petForm.species);
    const path =
      petFormMode === "edit"
        ? `/v1/users/${encodeURIComponent(userId)}/pets/${encodeURIComponent(targetPetId)}`
        : `/v1/users/${encodeURIComponent(userId)}/pets`;
    const savedPetForm = {
      ...petForm,
      ...(petForm.avatarImage
        ? {
            avatarImage: await cropAvatarImage(petForm),
            avatarZoom: "1",
            avatarX: "50",
            avatarY: "50",
          }
        : {}),
    };
    await api(path, {
      method: petFormMode === "edit" ? "PATCH" : "POST",
      body: {
        dog_profile: {
          id: targetPetId,
          species: savedPetForm.species || "dog",
          name: savedPetForm.name.trim(),
          breed: savedPetForm.breed || null,
          age_years: savedPetForm.ageYears ? Number(savedPetForm.ageYears) : null,
          weight_kg: savedPetForm.weightKg ? Number(savedPetForm.weightKg) : null,
          care_notes: avatarCareNotes(savedPetForm),
        },
        behavioral_baseline: {},
        health_baseline: {
          normal_appetite: savedPetForm.normalAppetite || "unknown",
          normal_stool_quality: savedPetForm.normalStool || "unknown",
          normal_activity_level: savedPetForm.normalActivity || "unknown",
          known_medical_notes: savedPetForm.medicalNotes
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean),
        },
      },
    });
    setPetFormOpen(false);
    setPetForm(blankPetForm);
    await loadPets(userId, targetPetId);
  }

  async function sendMessage(messageText: string, existingMessageId?: string) {
    if (!userId || !selectedPetId || !messageText.trim()) return;
    setIsSending(true);
    const workingId = existingMessageId || addChat("assistant", "Received your update.", "working");
    try {
      const streamed = await sendPetMessageStream(
        userId,
        selectedPetId,
        messageText,
        (status) => {
          updateChat(
            workingId,
            status.message || statusLabel(status.stage),
            "working",
          );
        },
      );
      renderAssistantResponse(
        workingId,
        streamed.response,
        streamed.care_context,
      );
    } catch {
      removeChat(workingId);
      const response = await api<UserResponse>(
        `/v1/users/${encodeURIComponent(userId)}/pets/${encodeURIComponent(
          selectedPetId,
        )}/messages`,
        {
          method: "POST",
          body: { raw_text: messageText, timestamp: new Date().toISOString() },
        },
      );
      const careContext = await fetchCareContext(messageText);
      addAssistantResponse(response, careContext);
    } finally {
      setIsSending(false);
      await loadPets(userId, selectedPetId);
      await refreshObservations();
    }
  }

  async function handleMessageSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = rawText.trim();
    if (!message) {
      setNotice("Message is required.");
      return;
    }
    addChat("user", message);
    setRawText("");
    await sendMessage(message);
  }

  async function handleObservationSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPetId) {
      setNotice("Choose a pet before saving an observation.");
      return;
    }
    if (!observationDetails.trim()) {
      setNotice("Observation details are required.");
      return;
    }
    const duplicate = duplicateMealWarning(observationDetails, observations);
    if (duplicate && pendingDuplicateMeal !== duplicate) {
      setPendingDuplicateMeal(duplicate);
      setDuplicateWarning(duplicate);
      return;
    }
    const message = `${observationDetails.trim()} Category: ${observationCategory}. Severity: ${observationSeverity}.`;
    addChat("user", observationDetails.trim());
    setObservationDetails("");
    setDuplicateWarning("");
    setPendingDuplicateMeal("");
    await sendMessage(message);
    setView("timeline");
  }

  async function refreshObservations() {
    if (!userId || !selectedPetId) return;
    const result = await api<{ observations: Observation[] }>(
      `/v1/users/${encodeURIComponent(userId)}/pets/${encodeURIComponent(
        selectedPetId,
      )}/observations`,
    );
    setObservations(result.observations);
  }

  async function fetchCareContext(messageText: string): Promise<CareContext> {
    if (!userId || !selectedPetId) return {};
    return api<CareContext>(
      `/v1/users/${encodeURIComponent(userId)}/pets/${encodeURIComponent(
        selectedPetId,
      )}/care-context`,
      {
        method: "POST",
        body: { raw_text: messageText, limit: 3 },
      },
    );
  }

  function ensureChatForPet(petId: string, pet: PetSummary | null) {
    setChatByPetId((current) => {
      if (current[petId]) return current;
      return { ...current, [petId]: [assistantGreeting(pet)] };
    });
  }

  function addChat(
    role: "assistant" | "user",
    message: string,
    status = "",
    meta: string[] = [],
    careContext: CareContext | null = null,
  ) {
    const id = `${role}_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const petKey = selectedPetId || "_system";
    const chatMessage = { id, role, message, status, meta, careContext };
    setChatByPetId((current) => ({
      ...current,
      [petKey]: [...(current[petKey] || [assistantGreeting(selectedPet)]), chatMessage],
    }));
    return id;
  }

  function updateChat(
    messageId: string,
    message: string,
    status = "",
    meta: string[] = [],
    careContext: CareContext | null = null,
  ) {
    const petKey = selectedPetId || "_system";
    setChatByPetId((current) => ({
      ...current,
      [petKey]: (current[petKey] || []).map((item) =>
        item.id === messageId ? { ...item, message, status, meta, careContext } : item,
      ),
    }));
  }

  function removeChat(messageId: string) {
    const petKey = selectedPetId || "_system";
    setChatByPetId((current) => ({
      ...current,
      [petKey]: (current[petKey] || []).filter((item) => item.id !== messageId),
    }));
  }

  function addAssistantResponse(response: UserResponse, careContext: CareContext) {
    addChat(
      "assistant",
      response.message,
      response.status,
      responseMeta(response),
      careContext,
    );
  }

  function renderAssistantResponse(
    messageId: string,
    response: UserResponse,
    careContext: CareContext,
  ) {
    updateChat(
      messageId,
      response.message,
      response.status,
      responseMeta(response),
      careContext,
    );
  }

  function openPetForm(mode: "create" | "edit") {
    setPetFormMode(mode);
    if (mode === "edit" && selectedPetDetail) {
      setPetForm(petFormFromDetail(selectedPetDetail));
    } else {
      setPetForm(blankPetForm);
    }
    setPetFormOpen(true);
  }

  function openCarePlanEditor() {
    if (!selectedPetId) {
      setNotice("Choose a pet before editing a care plan.");
      return;
    }
    setCareDraft(structuredClone(carePlanForPet(selectedPetId, carePlanByPetId)));
    setCarePlanEditing(true);
    setView("care");
  }

  function saveCarePlan() {
    if (!selectedPetId) return;
    setCarePlanByPetId((current) => ({ ...current, [selectedPetId]: careDraft }));
    setCarePlanEditing(false);
  }

  const carePlan = useMemo(
    () => carePlanForPet(selectedPetId, carePlanByPetId),
    [selectedPetId, carePlanByPetId],
  );

  const workspaceTitle = titleForView(view, selectedPet);
  const workspaceEyebrow = eyebrowForView(view, selectedPet);

  return (
    <main className="app-shell">
      <aside className="home-screen" aria-label="Workspace">
        <div className="app-topbar">
          <div className="brand">
            <div className="brand-mark" aria-hidden="true">P</div>
            <h1>PawCare</h1>
          </div>
          <div className="notification-dot" aria-hidden="true" />
        </div>

        <section className="hero-copy">
          <h2>{userId ? `Hi, ${displayName || "there"}` : "Welcome"}</h2>
          <p>{userId ? "How is your pet doing today?" : "Create your local workspace."}</p>
        </section>

        {!userId && (
          <form className="profile-card" onSubmit={handleWorkspaceSubmit}>
            <label>
              Name
              <input
                value={displayName}
                required
                autoComplete="name"
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
            <label>
              Email
              <input
                value={email}
                type="email"
                required
                autoComplete="email"
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <button type="submit">Enter workspace</button>
          </form>
        )}

        <section className="home-section">
          <div className="section-title">
            <h3>Pets</h3>
            <span>{pets.length}</span>
          </div>
          <section className="pet-strip" aria-label="Pets">
            {pets.length ? (
              pets.map((pet) => (
                <button
                  key={pet.pet_id}
                  className={`pet-button ${pet.pet_id === selectedPetId ? "active" : ""}`}
                  type="button"
                  onClick={() => void selectPet(pet.pet_id)}
                >
                  <PetAvatar pet={pet} />
                  <span className="pet-card-body">
                    <strong>{pet.name || pet.pet_id}</strong>
                    <span className="pet-card-meta">
                      {speciesLabel(pet.species)} · Last check-in{" "}
                      {pet.observation_count ? "today" : "not yet"}
                    </span>
                    <span className={`pet-status ${pet.observation_count ? "updated" : ""}`}>
                      {pet.observation_count ? "Updated" : "Good"}
                    </span>
                  </span>
                </button>
              ))
            ) : (
              <article className="empty-pets">
                <strong>No pets yet</strong>
                <span>Add a pet profile to start logging updates.</span>
              </article>
            )}
          </section>
          <button
            className="add-pet-button"
            type="button"
            disabled={!userId}
            onClick={() => openPetForm("create")}
          >
            Add pet
          </button>
        </section>

        <section className="summary-section">
          <h3>Today's Summary</h3>
          <div className="summary-grid">
            <article><strong>{totalObservations}</strong><span>Observations</span></article>
            <article><strong>{alertCount}</strong><span>Alerts</span></article>
            <article><strong>{pets.length}</strong><span>Pets</span></article>
            <article><strong>{pets.length ? "92%" : "--"}</strong><span>Wellness</span></article>
          </div>
        </section>

        <button
          className="assistant-card"
          type="button"
          disabled={!pets.length}
          onClick={() => {
            const targetPetId = selectedPetId || pets[0]?.pet_id;
            if (targetPetId) void selectPet(targetPetId);
          }}
        >
          <div>
            <h3>AI Health Assistant</h3>
            <p>Choose a pet and open a private care chat.</p>
          </div>
          <div className="bot-mark" aria-hidden="true" />
        </button>

        {petFormOpen && (
          <PetProfileForm
            mode={petFormMode}
            value={petForm}
            onChange={setPetForm}
            onSubmit={handlePetSubmit}
            onClose={() => setPetFormOpen(false)}
          />
        )}

        <BottomNav view={view} onViewChange={setView} />
      </aside>

      <section className="workspace" aria-label="Pet message workspace">
        <header className="workspace-header">
          <button className="back-button" type="button" aria-label="Back" onClick={() => setView("home")}>
            ‹
          </button>
          {selectedPet && <PetAvatar pet={selectedPet} variant="header" />}
          <div>
            <p className="eyebrow">{workspaceEyebrow}</p>
            <h2>{workspaceTitle}</h2>
          </div>
          <button
            className="icon-menu-button"
            type="button"
            aria-label="Refresh"
            disabled={!userId}
            onClick={() => void loadPets(userId, selectedPetId)}
          >
            ⋮
          </button>
        </header>

        {notice && (
          <div className="notice-banner">
            <span>{notice}</span>
            <button className="secondary-button small-action" type="button" onClick={() => setNotice("")}>
              Dismiss
            </button>
          </div>
        )}

        {view === "home" && (
          <section className="app-view active">
            <section className="chat-screen">
              <div className="chat-thread" aria-live="polite">
                {currentChat.map((message) => (
                  <ChatBubble key={message.id} message={message} />
                ))}
                <div ref={chatEndRef} />
              </div>
              <div className="quick-actions">
                <button
                  className="secondary-button"
                  type="button"
                  disabled={!selectedPetId}
                  onClick={() => setView("observe")}
                >
                  Add Observation
                </button>
                <button className="secondary-button" type="button" onClick={() => setView("timeline")}>
                  Timeline
                </button>
                <button className="secondary-button" type="button" onClick={() => setView("care")}>
                  Care Plan
                </button>
              </div>
              {selectedPet && (
                <form className="chat-composer" onSubmit={handleMessageSubmit}>
                  <button
                    className="secondary-button icon-button"
                    type="button"
                    onClick={() => setView("observe")}
                  >
                    +
                  </button>
                  <input
                    value={rawText}
                    placeholder="Type a message..."
                    required
                    autoComplete="off"
                    onChange={(event) => setRawText(event.target.value)}
                  />
                  <button className="send-button" type="submit" disabled={isSending}>
                    Send
                  </button>
                </form>
              )}
            </section>
          </section>
        )}

        {view === "observe" && (
          <AddObservationView
            category={observationCategory}
            details={observationDetails}
            severity={observationSeverity}
            duplicateWarning={duplicateWarning}
            onCategoryChange={setObservationCategory}
            onDetailsChange={setObservationDetails}
            onSeverityChange={setObservationSeverity}
            onSubmit={handleObservationSubmit}
            onBack={() => setView("home")}
          />
        )}

        {view === "timeline" && (
          <TimelineView observations={observations} onBack={() => setView("home")} />
        )}

        {view === "care" && (
          <CarePlanView
            plan={carePlan}
            editing={carePlanEditing}
            draft={careDraft}
            onEdit={openCarePlanEditor}
            onDraftChange={setCareDraft}
            onSave={saveCarePlan}
            onCancel={() => setCarePlanEditing(false)}
          />
        )}

        {view === "profile" && (
          <ProfileView
            pet={selectedPet}
            detail={selectedPetDetail}
            onEdit={() => openPetForm("edit")}
          />
        )}

        <BottomNav view={view} onViewChange={setView} className="workspace-nav" />
      </section>
    </main>
  );
}

function PetProfileForm({
  mode,
  value,
  onChange,
  onSubmit,
  onClose,
}: {
  mode: "create" | "edit";
  value: PetFormState;
  onChange: (value: PetFormState) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClose: () => void;
}) {
  const breeds = value.species === "cat" ? catBreeds : dogBreeds;
  const avatarDragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    avatarX: number;
    avatarY: number;
  } | null>(null);
  function patch(update: Partial<PetFormState>) {
    onChange({ ...value, ...update });
  }
  function startAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    if (!value.avatarImage) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    avatarDragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      avatarX: Number(value.avatarX) || 50,
      avatarY: Number(value.avatarY) || 50,
    };
  }
  function moveAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    const drag = avatarDragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const zoom = Number(value.avatarZoom) || 1;
    const sensitivity = 0.7 / zoom;
    patch({
      avatarX: String(Math.round(clamp(drag.avatarX + (event.clientX - drag.startX) * sensitivity, 0, 100))),
      avatarY: String(Math.round(clamp(drag.avatarY + (event.clientY - drag.startY) * sensitivity, 0, 100))),
    });
  }
  function stopAvatarDrag(event: PointerEvent<HTMLDivElement>) {
    const drag = avatarDragRef.current;
    if (drag?.pointerId === event.pointerId) {
      avatarDragRef.current = null;
    }
  }
  return (
    <section className="profile-card">
      <div className="section-title">
        <h2>{mode === "edit" ? "Edit profile" : "Add pet"}</h2>
        <button className="secondary-button" type="button" onClick={onClose}>Close</button>
      </div>
      <form className="stacked-form" onSubmit={onSubmit}>
        <label>Name<input value={value.name} required onChange={(event) => patch({ name: event.target.value })} /></label>
        <label>
          Species
          <select value={value.species} onChange={(event) => patch({ species: event.target.value, breed: "", avatar: event.target.value === "cat" ? "cat" : "collie" })}>
            <option value="dog">Dog</option>
            <option value="cat">Cat</option>
          </select>
        </label>
        <fieldset>
          <legend>Avatar</legend>
          <div className="avatar-picker">
            {["collie", "golden", "black", "cat"].map((avatar) => (
              <label key={avatar}>
                <input
                  type="radio"
                  name="avatar"
                  value={avatar}
                  checked={value.avatar === avatar}
                  onChange={() => patch({ avatar })}
                />
                <span className={`avatar-choice avatar-${avatar}`} />
              </label>
            ))}
          </div>
          <div className="avatar-upload">
            <label>
              Use local photo
              <input
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (!file) {
                    patch({ avatarImage: "" });
                    return;
                  }
                  const reader = new FileReader();
                  reader.addEventListener("load", () =>
                    patch({
                      avatarImage: String(reader.result || ""),
                      avatarZoom: "1.15",
                      avatarX: "50",
                      avatarY: "50",
                    }),
                  );
                  reader.readAsDataURL(file);
                }}
              />
            </label>
            <div
              className={`avatar-image-preview ${value.avatarImage ? "draggable" : ""}`}
              onPointerDown={startAvatarDrag}
              onPointerMove={moveAvatarDrag}
              onPointerUp={stopAvatarDrag}
              onPointerCancel={stopAvatarDrag}
            >
              {value.avatarImage ? (
                <>
                  <AvatarPhoto
                    src={value.avatarImage}
                    zoom={Number(value.avatarZoom)}
                    x={Number(value.avatarX)}
                    y={Number(value.avatarY)}
                  />
                  <span>Drag to reposition</span>
                </>
              ) : "No photo selected"}
            </div>
            {value.avatarImage && (
              <div className="avatar-crop-controls">
                <label>
                  Zoom
                  <input
                    type="range"
                    min="1"
                    max="2.4"
                    step="0.05"
                    value={value.avatarZoom}
                    onChange={(event) => patch({ avatarZoom: event.target.value })}
                  />
                </label>
                <p className="avatar-crop-hint">Drag the photo inside the frame to choose the avatar area.</p>
                <button
                  className="secondary-button small-action"
                  type="button"
                  onClick={() => patch({ avatarImage: "", avatarZoom: "1", avatarX: "50", avatarY: "50" })}
                >
                  Remove photo
                </button>
              </div>
            )}
          </div>
        </fieldset>
        <div className="field-row">
          <label>
            Breed
            <select value={value.breed} onChange={(event) => patch({ breed: event.target.value })}>
              {breeds.map(([optionValue, label]) => (
                <option key={optionValue} value={optionValue}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            Age
            <select value={value.ageYears} onChange={(event) => patch({ ageYears: event.target.value })}>
              {ageOptions.map(([optionValue, label]) => (
                <option key={optionValue} value={optionValue}>{label}</option>
              ))}
            </select>
          </label>
        </div>
        <label>
          Weight kg
          <input value={value.weightKg} type="number" min="0" step="0.1" onChange={(event) => patch({ weightKg: event.target.value })} />
        </label>
        <fieldset>
          <legend>Health baseline</legend>
          <div className="field-row">
            <label>
              Normal appetite
              <select value={value.normalAppetite} onChange={(event) => patch({ normalAppetite: event.target.value })}>
                <option value="unknown">Unknown</option>
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="picky">Picky</option>
              </select>
            </label>
            <label>
              Normal stool
              <select value={value.normalStool} onChange={(event) => patch({ normalStool: event.target.value })}>
                <option value="unknown">Unknown</option>
                <option value="firm">Firm</option>
                <option value="soft">Soft</option>
                <option value="loose">Loose</option>
                <option value="variable">Variable</option>
              </select>
            </label>
          </div>
          <label>
            Normal activity
            <select value={value.normalActivity} onChange={(event) => patch({ normalActivity: event.target.value })}>
              <option value="unknown">Unknown</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="very_high">Very high</option>
            </select>
          </label>
          <label>
            Medical notes
            <textarea value={value.medicalNotes} rows={3} onChange={(event) => patch({ medicalNotes: event.target.value })} />
          </label>
        </fieldset>
        <button type="submit">{mode === "edit" ? "Update profile" : "Save profile"}</button>
      </form>
    </section>
  );
}

function AddObservationView({
  category,
  details,
  severity,
  duplicateWarning,
  onCategoryChange,
  onDetailsChange,
  onSeverityChange,
  onSubmit,
  onBack,
}: {
  category: string;
  details: string;
  severity: string;
  duplicateWarning: string;
  onCategoryChange: (value: string) => void;
  onDetailsChange: (value: string) => void;
  onSeverityChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onBack: () => void;
}) {
  const categories = ["appetite", "energy", "stool", "vomiting", "coughing", "skin", "behavior", "other"];
  return (
    <section className="app-view add-observation-panel active">
      <div className="section-title">
        <h3>Add Observation</h3>
        <button className="secondary-button" type="button" onClick={onBack}>Back</button>
      </div>
      <form className="observation-form" onSubmit={onSubmit}>
        <fieldset>
          <legend>What did you notice?</legend>
          <div className="observation-types">
            {categories.map((item) => (
              <label key={item}>
                <input type="radio" name="category" value={item} checked={category === item} onChange={() => onCategoryChange(item)} />
                <span>{labelForCategory(item)}</span>
              </label>
            ))}
          </div>
        </fieldset>
        <label>
          Details
          <textarea
            value={details}
            rows={5}
            placeholder="Heidou ate less than usual at breakfast."
            required
            onChange={(event) => onDetailsChange(event.target.value)}
          />
        </label>
        <fieldset>
          <legend>Severity</legend>
          <div className="severity-control">
            {["mild", "moderate", "severe"].map((item) => (
              <label key={item}>
                <input type="radio" name="severity" value={item} checked={severity === item} onChange={() => onSeverityChange(item)} />
                <span>{labelForCategory(item)}</span>
              </label>
            ))}
          </div>
        </fieldset>
        {duplicateWarning && <div className="duplicate-warning">{duplicateWarning}</div>}
        <section className="photo-row" aria-label="Photos">
          <strong>Add Photos</strong>
          <div>
            <span className="avatar-choice avatar-cat" />
            <span className="avatar-choice avatar-collie" />
            <button className="secondary-button photo-add" type="button">+</button>
          </div>
        </section>
        <button type="submit">Save Observation</button>
      </form>
    </section>
  );
}

function TimelineView({ observations, onBack }: { observations: Observation[]; onBack: () => void }) {
  const grouped = groupObservationsByDay([...observations].reverse());
  return (
    <section className="app-view observations-panel active">
      <div className="timeline-head">
        <button className="back-button" type="button" aria-label="Back" onClick={onBack}>‹</button>
        <h3>Health Timeline</h3>
        <button className="filter-button" type="button" aria-label="Filter">⌯</button>
      </div>
      <div className="timeline-tabs" aria-label="Timeline filters">
        <span className="active">All</span><span>Observations</span><span>Notes</span><span>Alerts</span>
      </div>
      <span className="observation-count-badge">{observations.length}</span>
      <div className="observations-list">
        {grouped.length ? grouped.map((group) => (
          <section key={group.label} className="timeline-day">
            <h4>{group.label}</h4>
            {group.items.map((observation) => (
              <div key={observation.observation_id} className="timeline-entry">
                <time className="timeline-time">{timeLabel(observation.timestamp)}</time>
                <span className="timeline-dot" aria-hidden="true">{dotLabel(observation.category)}</span>
                <article className="observation-item">
                  <div className="observation-item-header">
                    <strong>{labelForCategory(observation.category)}</strong>
                    <span>{timeLabel(observation.timestamp)}</span>
                  </div>
                  <p>{observation.raw_text}</p>
                  <span className={`pet-status ${statusClassForObservation(observation)}`}>
                    {statusTextForObservation(observation)}
                  </span>
                </article>
              </div>
            ))}
          </section>
        )) : <p className="empty-state">No observations recorded.</p>}
      </div>
    </section>
  );
}

function CarePlanView({
  plan,
  editing,
  draft,
  onEdit,
  onDraftChange,
  onSave,
  onCancel,
}: {
  plan: CarePlan;
  editing: boolean;
  draft: CarePlan;
  onEdit: () => void;
  onDraftChange: (plan: CarePlan) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <section className="app-view care-plan-panel active">
      <article className="routine-card">
        <div className="care-card-title">
          <h3>Daily Routine</h3>
          <button className="secondary-button small-action" type="button" onClick={onEdit}>Modify</button>
        </div>
        <ul>
          {plan.routines.map((routine, index) => (
            <li key={`${routine.label}-${index}`}>
              <span className={index === 0 ? "done" : ""} />
              <strong>{routine.label}</strong>
              <time>{formatCareValue(routine.value)}</time>
            </li>
          ))}
        </ul>
      </article>
      <article className="routine-card">
        <div className="care-card-title">
          <h3>Medications</h3>
          <button className="secondary-button small-action" type="button" onClick={onEdit}>Modify</button>
        </div>
        <div>
          {plan.medications.map((medication, index) => (
            <div key={`${medication.name}-${index}`} className="medication-row">
              <span className="medicine-dot" />
              <div><strong>{medication.name}</strong><p>{medication.note}</p></div>
            </div>
          ))}
        </div>
      </article>
      {editing && (
        <CarePlanEditor
          draft={draft}
          onChange={onDraftChange}
          onSave={onSave}
          onCancel={onCancel}
        />
      )}
    </section>
  );
}

function CarePlanEditor({
  draft,
  onChange,
  onSave,
  onCancel,
}: {
  draft: CarePlan;
  onChange: (plan: CarePlan) => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  function updateRoutine(index: number, field: "label" | "value", value: string) {
    const routines = draft.routines.map((routine, currentIndex) =>
      currentIndex === index ? { ...routine, [field]: value } : routine,
    );
    onChange({ ...draft, routines });
  }
  function updateMedication(index: number, field: "name" | "note", value: string) {
    const medications = draft.medications.map((medication, currentIndex) =>
      currentIndex === index ? { ...medication, [field]: value } : medication,
    );
    onChange({ ...draft, medications });
  }
  return (
    <form className="care-plan-form" onSubmit={(event) => { event.preventDefault(); onSave(); }}>
      <h3>Modify Care Plan</h3>
      <section className="dynamic-care-section">
        <div className="care-card-title">
          <h4>Routines</h4>
          <button className="secondary-button small-action" type="button" onClick={() => onChange({ ...draft, routines: [...draft.routines, { label: "", value: "" }] })}>
            Add routine
          </button>
        </div>
        <div className="dynamic-fields">
          {draft.routines.map((routine, index) => (
            <div key={index} className="dynamic-row">
              <input placeholder="Routine name" value={routine.label} onChange={(event) => updateRoutine(index, "label", event.target.value)} />
              <input placeholder="Time or frequency" value={routine.value} onChange={(event) => updateRoutine(index, "value", event.target.value)} />
              <button className="secondary-button remove-row-button" type="button" onClick={() => onChange({ ...draft, routines: draft.routines.filter((_, currentIndex) => currentIndex !== index) })}>
                Remove
              </button>
            </div>
          ))}
        </div>
      </section>
      <section className="dynamic-care-section">
        <div className="care-card-title">
          <h4>Medications</h4>
          <button className="secondary-button small-action" type="button" onClick={() => onChange({ ...draft, medications: [...draft.medications, { name: "", note: "" }] })}>
            Add medication
          </button>
        </div>
        <div className="dynamic-fields">
          {draft.medications.map((medication, index) => (
            <div key={index} className="dynamic-row medication-edit-row">
              <input placeholder="Medication name" value={medication.name} onChange={(event) => updateMedication(index, "name", event.target.value)} />
              <input placeholder="When / how often" value={medication.note} onChange={(event) => updateMedication(index, "note", event.target.value)} />
              <button className="secondary-button remove-row-button" type="button" onClick={() => onChange({ ...draft, medications: draft.medications.filter((_, currentIndex) => currentIndex !== index) })}>
                Remove
              </button>
            </div>
          ))}
        </div>
      </section>
      <div className="care-form-actions">
        <button type="submit">Save plan</button>
        <button className="secondary-button" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function ProfileView({
  pet,
  detail,
  onEdit,
}: {
  pet: PetSummary | null;
  detail: PetDetail | null;
  onEdit: () => void;
}) {
  return (
    <section className="app-view profile-panel active">
      <div className="profile-hero">
        {pet ? <PetAvatar pet={pet} variant="profile" /> : <div className="profile-avatar">P</div>}
        <h3>{pet?.name || "No pet selected"}</h3>
        <p>{pet ? `${speciesLabel(pet.species)} · ${pet.observation_count} observations` : "Choose a pet from Home."}</p>
      </div>
      <div className="meta-list">
        <p><strong>Breed:</strong> {detail?.dog_profile.breed || "Unknown"}</p>
        <p><strong>Age:</strong> {detail?.dog_profile.age_years || "Unknown"}</p>
        <p><strong>Normal appetite:</strong> {detail?.health_baseline.normal_appetite || "Unknown"}</p>
      </div>
      <div className="settings-list">
        <button type="button" disabled={!pet} onClick={onEdit}>Basic Info & Edit</button>
        <button type="button">Medical History</button>
        <button type="button">Vaccinations</button>
        <button type="button">Allergies</button>
        <button type="button">Documents</button>
        <button type="button">Caregivers</button>
        <button type="button">Notifications</button>
      </div>
    </section>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return <article className="chat-bubble user"><p>{message.message}</p></article>;
  }
  return (
    <article className="chat-bubble assistant">
      <div className="assistant-avatar" aria-hidden="true">🤖</div>
      <div>
        <strong>PawCare Assistant</strong>
        {message.status && <span className={`status-pill ${message.status}`}>{message.status}</span>}
        <p>{message.message}</p>
        {message.meta?.length ? <ul>{message.meta.map((line) => <li key={line}>{line}</li>)}</ul> : null}
        <CareContextCards careContext={message.careContext || null} />
      </div>
    </article>
  );
}

function CareContextCards({ careContext }: { careContext: CareContext | null }) {
  const references = careContext?.professional_references || [];
  const relatedCases = careContext?.related_cases || [];
  const screeningChecklist = careContext?.screening_checklist || null;
  const [expanded, setExpanded] = useState(false);
  const visibleReferences = expanded ? references : references.slice(0, 1);
  const visibleRelatedCases = expanded ? relatedCases : relatedCases.slice(0, 1);
  const hiddenCardCount = references.length + relatedCases.length - visibleReferences.length - visibleRelatedCases.length;
  if (!careContext?.context_summary && !screeningChecklist && !references.length && !relatedCases.length) return null;
  return (
    <section className="related-cases" aria-label="Care context">
      <div className="related-cases-header">
        <strong>Care context</strong>
        <span>Not a diagnosis</span>
      </div>
      {careContext?.non_diagnostic_notice && <p className="case-disclaimer">{careContext.non_diagnostic_notice}</p>}
      {screeningChecklist && <ScreeningChecklistCard checklist={screeningChecklist} />}
      {careContext?.context_summary && <p className="context-summary">{careContext.context_summary}</p>}
      <div className="case-card-list">
        {visibleReferences.map((item, index) => (
          <article key={`ref-${index}`} className="case-card professional-reference-card">
            <div className="case-card-topline"><span>Vet reference</span><span>{item.relevance_level || "related"}</span></div>
            <h4>{item.source_name || "Professional reference"}</h4>
            <p>{item.summary || ""}</p>
            {item.vet_discussion_topics?.length ? <p><strong>Discuss with vet:</strong> {item.vet_discussion_topics.slice(0, 4).join(", ")}</p> : null}
            {item.what_to_record?.length ? <p><strong>Record before visit:</strong> {item.what_to_record.slice(0, 5).join(", ")}</p> : null}
            {item.red_flags?.length ? <p><strong>Watch urgently for:</strong> {item.red_flags.slice(0, 3).join("; ")}</p> : null}
            <SafeLink href={item.source_url} label="Open reference" />
          </article>
        ))}
        {visibleRelatedCases.map((item, index) => (
          <article key={`case-${index}`} className="case-card">
            <div className="case-card-topline"><span>Similar case</span><span>{item.condition_discussion_priority || "discussion topic"}</span></div>
            <h4>{item.title || "Related pet case"}</h4>
            <p>{item.case_summary || ""}</p>
            {item.matched_symptoms?.length ? <p><strong>Matched signs:</strong> {item.matched_symptoms.join(", ")}</p> : null}
            {item.possible_discussion_topics?.length ? <p><strong>Vet discussion topics:</strong> {item.possible_discussion_topics.join(", ")}</p> : null}
            {item.red_flags?.length ? <p><strong>Watch urgently for:</strong> {item.red_flags.slice(0, 3).join("; ")}</p> : null}
            <SafeLink href={item.source_url} label="Open original source" />
          </article>
        ))}
      </div>
      {hiddenCardCount > 0 && (
        <button className="secondary-button small-action view-more-context" type="button" onClick={() => setExpanded(!expanded)}>
          {expanded ? "Show less" : `View ${hiddenCardCount} more ${hiddenCardCount === 1 ? "card" : "cards"}`}
        </button>
      )}
    </section>
  );
}

function ScreeningChecklistCard({ checklist }: { checklist: NonNullable<CareContext["screening_checklist"]> }) {
  return (
    <article className="case-card screening-checklist-card">
      <div className="case-card-topline">
        <span>Screening checklist</span>
        <span>{screeningSourceLabel(checklist.source)} · {labelForCategory(checklist.possible_domain || "review")}</span>
      </div>
      {checklist.non_diagnostic_notice && <p>{checklist.non_diagnostic_notice}</p>}
      {checklist.symptom_checklist?.length ? (
        <ChecklistSection title="Check whether you see" items={checklist.symptom_checklist} />
      ) : null}
      {checklist.questions_to_ask_user?.length ? (
        <ChecklistSection title="Questions to answer" items={checklist.questions_to_ask_user} />
      ) : null}
      {checklist.safe_next_steps?.length ? (
        <ChecklistSection title="Safe next steps" items={checklist.safe_next_steps} />
      ) : null}
    </article>
  );
}

function screeningSourceLabel(source?: string) {
  return source === "llm_screening" ? "AI screening" : "Rule-based screening";
}

function ChecklistSection({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="checklist-section">
      <strong>{title}</strong>
      <ul>
        {items.slice(0, 6).map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function SafeLink({ href, label }: { href?: string; label: string }) {
  if (!href || (!href.startsWith("https://") && !href.startsWith("http://"))) return null;
  return <a href={href} target="_blank" rel="noopener noreferrer">{label}</a>;
}

function BottomNav({
  view,
  onViewChange,
  className = "",
}: {
  view: View;
  onViewChange: (view: View) => void;
  className?: string;
}) {
  return (
    <nav className={`bottom-nav ${className}`} aria-label="Primary">
      {(["home", "timeline", "care", "profile"] as View[]).map((item) => (
        <button
          key={item}
          className={`nav-item ${view === item ? "active" : ""}`}
          type="button"
          onClick={() => onViewChange(item)}
        >
          {item === "home" ? "Home" : item === "timeline" ? "Timeline" : item === "care" ? "Care Plan" : "Profile"}
        </button>
      ))}
    </nav>
  );
}

function PetAvatar({ pet, variant = "card" }: { pet: PetSummary; variant?: "card" | "header" | "profile" }) {
  const className =
    variant === "profile"
      ? `profile-avatar ${avatarClass(pet.avatar)}`
      : `${variant === "header" ? "header-pet-avatar " : ""}pet-avatar ${avatarClass(pet.avatar)}`;
  return (
    <span
      className={`${className} ${pet.avatar_image ? "has-image" : ""}`}
      aria-hidden="true"
    >
      {pet.avatar_image && (
        <AvatarPhoto
          src={pet.avatar_image}
          zoom={pet.avatar_zoom || 1}
          x={pet.avatar_x || 50}
          y={pet.avatar_y || 50}
        />
      )}
    </span>
  );
}

function AvatarPhoto({ src, zoom = 1, x = 50, y = 50 }: { src: string; zoom?: number | null; x?: number | null; y?: number | null }) {
  return (
    <img
      className="avatar-photo"
      src={src}
      alt=""
      draggable={false}
      style={avatarImageStyle({ avatar_zoom: zoom, avatar_x: x, avatar_y: y })}
    />
  );
}

function responseMeta(response: UserResponse) {
  return [
    response.risk_band ? `Risk: ${response.risk_band}` : "",
    response.source_guideline_ids?.length ? `Guidelines: ${response.source_guideline_ids.join(", ")}` : "",
    response.escalation_conditions?.length ? `Escalation: ${response.escalation_conditions.join("; ")}` : "",
  ].filter(Boolean);
}

async function sendPetMessageStream(
  userId: string,
  petId: string,
  messageText: string,
  onStatus: (status: { stage?: string; message?: string }) => void,
): Promise<{ response: UserResponse; care_context: CareContext }> {
  const response = await fetch(
    `/v1/users/${encodeURIComponent(userId)}/pets/${encodeURIComponent(petId)}/messages/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ raw_text: messageText, timestamp: new Date().toISOString() }),
    },
  );
  if (!response.ok || !response.body) throw new Error("Streaming request failed.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload: unknown = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    blocks.forEach((block) => {
      const event = parseSseBlock(block);
      if (!event) return;
      if (event.event === "status") onStatus(event.data || {});
      if (event.event === "final") finalPayload = event.data;
    });
  }
  if (!isStreamFinalPayload(finalPayload)) {
    throw new Error("Streaming response did not include a final message.");
  }
  return finalPayload;
}

function isStreamFinalPayload(
  value: unknown,
): value is { response: UserResponse; care_context: CareContext } {
  return Boolean(
    value &&
      typeof value === "object" &&
      "response" in value &&
      (value as { response?: unknown }).response,
  );
}

function parseSseBlock(block: string) {
  const lines = block.split("\n");
  let event = "message";
  const dataLines: string[] = [];
  lines.forEach((line) => {
    if (line.startsWith("event:")) event = line.slice("event:".length).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice("data:".length).trim());
  });
  if (!dataLines.length) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

async function api<T>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Request failed.";
    throw new Error(detail);
  }
  return data as T;
}

function defaultCarePlan(): CarePlan {
  return {
    routines: [
      { label: "Breakfast", value: "07:00" },
      { label: "Morning walk", value: "08:00" },
      { label: "Afternoon activity", value: "Play time at 4:00 PM" },
      { label: "Potty time", value: "Every 3 hours" },
      { label: "Potty before bed", value: "21:30" },
      { label: "Treat time", value: "2-3 times" },
      { label: "Dinner", value: "19:00" },
    ],
    medications: [{ name: "Probiotic", note: "Every morning after breakfast" }],
  };
}

function carePlanForPet(petId: string, plans: Record<string, CarePlan>) {
  return plans[petId] || defaultCarePlan();
}

function petFormFromDetail(detail: PetDetail): PetFormState {
  return {
    name: detail.dog_profile.name || "",
    species: detail.dog_profile.species || "dog",
    avatar: avatarFromCareNotes(detail.dog_profile.care_notes),
    avatarImage: avatarImageFromCareNotes(detail.dog_profile.care_notes),
    avatarZoom: avatarNumberFromCareNotes(detail.dog_profile.care_notes, "avatar_zoom", "1"),
    avatarX: avatarNumberFromCareNotes(detail.dog_profile.care_notes, "avatar_x", "50"),
    avatarY: avatarNumberFromCareNotes(detail.dog_profile.care_notes, "avatar_y", "50"),
    breed: detail.dog_profile.breed || "",
    ageYears: detail.dog_profile.age_years ? String(detail.dog_profile.age_years) : "",
    weightKg: detail.dog_profile.weight_kg ? String(detail.dog_profile.weight_kg) : "",
    normalAppetite: detail.health_baseline.normal_appetite || "unknown",
    normalStool: detail.health_baseline.normal_stool_quality || "unknown",
    normalActivity: detail.health_baseline.normal_activity_level || "unknown",
    medicalNotes: (detail.health_baseline.known_medical_notes || []).join("\n"),
  };
}

function avatarCareNotes(form: PetFormState) {
  const notes = [`avatar:${form.avatar || "collie"}`];
  if (form.avatarImage) {
    notes.push(`avatar_image:${form.avatarImage}`);
    notes.push(`avatar_zoom:${form.avatarZoom || "1"}`);
    notes.push(`avatar_x:${form.avatarX || "50"}`);
    notes.push(`avatar_y:${form.avatarY || "50"}`);
  }
  return notes;
}

function avatarFromCareNotes(notes: string[] = []) {
  return notes.find((note) => note.startsWith("avatar:"))?.replace("avatar:", "") || "collie";
}

function avatarImageFromCareNotes(notes: string[] = []) {
  return notes.find((note) => note.startsWith("avatar_image:"))?.replace("avatar_image:", "") || "";
}

async function cropAvatarImage(form: PetFormState): Promise<string> {
  if (!form.avatarImage) return "";
  const image = await loadImage(form.avatarImage);
  const size = 320;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  if (!context) return form.avatarImage;

  const zoom = clamp(Number(form.avatarZoom) || 1, 1, 2.4);
  const x = clamp(Number(form.avatarX) || 50, 0, 100);
  const y = clamp(Number(form.avatarY) || 50, 0, 100);
  const offsetX = ((x - 50) * 0.95 * size) / 100;
  const offsetY = ((y - 50) * 0.95 * size) / 100;
  const imageRatio = image.naturalWidth / image.naturalHeight;
  const canvasRatio = 1;
  const drawWidth = imageRatio > canvasRatio ? size * imageRatio : size;
  const drawHeight = imageRatio > canvasRatio ? size : size / imageRatio;

  context.save();
  context.translate(size / 2, size / 2);
  context.translate(offsetX, offsetY);
  context.scale(zoom, zoom);
  context.drawImage(image, -drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
  context.restore();
  return canvas.toDataURL("image/jpeg", 0.88);
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Unable to load avatar image."));
    image.src = src;
  });
}

function avatarNumberFromCareNotes(notes: string[] = [], key: string, fallback: string) {
  const value = notes.find((note) => note.startsWith(`${key}:`))?.replace(`${key}:`, "");
  return value && Number.isFinite(Number(value)) ? value : fallback;
}

function avatarImageStyle(pet: {
  avatar_zoom?: number | null;
  avatar_x?: number | null;
  avatar_y?: number | null;
}) {
  const zoom = clamp(Number(pet.avatar_zoom) || 1, 1, 2.4);
  const x = clamp(Number(pet.avatar_x) || 50, 0, 100);
  const y = clamp(Number(pet.avatar_y) || 50, 0, 100);
  const offsetX = (x - 50) * 0.95;
  const offsetY = (y - 50) * 0.95;
  return {
    transform: `translate(${offsetX}%, ${offsetY}%) scale(${zoom})`,
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function assistantGreeting(pet: PetSummary | null): ChatMessage {
  return {
    id: `assistant_greeting_${pet?.pet_id || "system"}`,
    role: "assistant",
    message: pet
      ? `You're chatting about ${pet.name || pet.pet_id}. Tell me meals, stool, energy, vomiting, behavior, or any care question.`
      : "Choose a pet, then tell me what happened.",
    status: "",
    meta: [],
  };
}

function restoreSession(): { user_id?: string; display_name?: string; selected_pet_id?: string } | null {
  try {
    return JSON.parse(localStorage.getItem(workspaceStorageKey) || "null");
  } catch {
    return null;
  }
}

function saveSession(payload: { user_id: string; display_name: string; selected_pet_id: string }) {
  localStorage.setItem(workspaceStorageKey, JSON.stringify(payload));
}

function restoreChatHistory(userId: string): Record<string, ChatMessage[]> {
  try {
    const parsed = JSON.parse(localStorage.getItem(chatStorageKey(userId)) || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const restored: Record<string, ChatMessage[]> = {};
    for (const [petId, messages] of Object.entries(parsed)) {
      if (!Array.isArray(messages)) continue;
      const safeMessages = messages.filter(isStoredChatMessage).slice(-80);
      if (safeMessages.length) restored[petId] = safeMessages;
    }
    return restored;
  } catch {
    return {};
  }
}

function saveChatHistory(userId: string, chatByPetId: Record<string, ChatMessage[]>) {
  const payload: Record<string, ChatMessage[]> = {};
  for (const [petId, messages] of Object.entries(chatByPetId)) {
    const safeMessages = messages.filter(isStoredChatMessage).slice(-80);
    if (safeMessages.length) payload[petId] = safeMessages;
  }
  localStorage.setItem(chatStorageKey(userId), JSON.stringify(payload));
}

function chatStorageKey(userId: string) {
  return `${chatStoragePrefix}:${userId}`;
}

function isStoredChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as Partial<ChatMessage>;
  return (
    typeof message.id === "string" &&
    (message.role === "assistant" || message.role === "user") &&
    typeof message.message === "string" &&
    (!message.status || typeof message.status === "string") &&
    (!message.meta || Array.isArray(message.meta)) &&
    (!message.careContext || typeof message.careContext === "object")
  );
}

function speciesLabel(species?: string | null) {
  return species === "cat" ? "Cat" : "Dog";
}

function generatePetId(name: string, species: string) {
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 32);
  return `${species === "cat" ? "cat" : "dog"}_${slug || "pet"}_${Date.now().toString(36)}`;
}

function avatarClass(avatar?: string | null) {
  const allowed = ["collie", "golden", "black", "cat"];
  return `avatar-${allowed.includes(avatar || "") ? avatar : "collie"}`;
}

function titleForView(view: View, pet: PetSummary | null) {
  if (view === "observe") return "Add Observation";
  if (view === "timeline") return "Health Timeline";
  if (view === "care") return "Care Plan";
  if (view === "profile") return pet?.name || "Profile";
  return pet?.name || "Your pets";
}

function eyebrowForView(view: View, pet: PetSummary | null) {
  if (view === "home") return pet ? "PawCare Assistant" : "Workspace";
  if (view === "profile") return "Profile";
  return pet?.name || "Workspace";
}

function labelForCategory(category: string) {
  return category.replace(/_/g, " ").replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function statusLabel(stage?: string) {
  const labels: Record<string, string> = {
    received: "Received your update.",
    loading_pet: "Loading pet workspace.",
    processing_message: "Checking health and behavior signals.",
    retrieving_care_context: "Retrieving care context.",
    safety_review: "Final safety review complete.",
  };
  return labels[stage || ""] || "Working on this update.";
}

function duplicateMealWarning(details: string, observations: Observation[]) {
  const meal = mealKeyword(details);
  if (!meal) return "";
  const today = new Date().toISOString().slice(0, 10);
  const duplicate = observations.some(
    (observation) =>
      observation.timestamp.startsWith(today) && mealKeyword(observation.raw_text) === meal,
  );
  return duplicate
    ? `There is already a ${meal} observation for today. Save again if this is a separate update.`
    : "";
}

function mealKeyword(value: string) {
  const normalized = value.toLowerCase();
  if (normalized.includes("breakfast")) return "breakfast";
  if (normalized.includes("lunch")) return "lunch";
  if (normalized.includes("dinner")) return "dinner";
  return "";
}

function groupObservationsByDay(observations: Observation[]) {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const todayKey = today.toISOString().slice(0, 10);
  const yesterdayKey = yesterday.toISOString().slice(0, 10);
  const groups: { label: string; items: Observation[] }[] = [];
  observations.forEach((observation) => {
    const key = observation.timestamp.slice(0, 10) || "unknown";
    let label = key;
    if (key === todayKey) label = "Today";
    if (key === yesterdayKey) label = "Yesterday";
    let group = groups.find((item) => item.label === label);
    if (!group) {
      group = { label, items: [] };
      groups.push(group);
    }
    group.items.push(observation);
  });
  return groups;
}

function timeLabel(timestamp: string) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function dotLabel(category: string) {
  if (category === "stool") return "S";
  if (category === "vomiting") return "V";
  if (category === "energy") return "E";
  if (category === "food_intake" || category === "appetite") return "A";
  return "O";
}

function statusTextForObservation(observation: Observation) {
  const raw = observation.raw_text.toLowerCase();
  if (raw.includes("bloody") || raw.includes("black") || raw.includes("vomit")) return "Attention Needed";
  if (raw.includes("less") || raw.includes("low") || raw.includes("tired")) return "Monitoring";
  return "Good";
}

function statusClassForObservation(observation: Observation) {
  const status = statusTextForObservation(observation);
  if (status === "Attention Needed") return "updated";
  if (status === "Monitoring") return "monitoring";
  return "";
}

function formatCareValue(value: string) {
  if (!/^\d{2}:\d{2}$/.test(value)) return value || "--";
  const [hoursRaw, minutes] = value.split(":");
  const hours = Number(hoursRaw);
  const suffix = hours >= 12 ? "PM" : "AM";
  return `${hours % 12 || 12}:${minutes} ${suffix}`;
}
