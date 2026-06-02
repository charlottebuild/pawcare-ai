const workspaceStorageKey = "pawcareWorkspaceV1";

const state = {
  userId: "",
  displayName: "",
  selectedPetId: "",
  selectedPetDetail: null,
  currentView: "home",
  petFormMode: "create",
  pets: [],
  observations: [],
  chatByPetId: {},
  carePlanByPetId: {},
  pendingAvatarImage: "",
  pendingDuplicateMeal: "",
};

const elements = {
  userForm: document.querySelector("#user-form"),
  petProfilePanel: document.querySelector("#pet-profile-panel"),
  petForm: document.querySelector("#pet-form"),
  petFormTitle: document.querySelector("#pet-form-title"),
  petFormSubmit: document.querySelector("#pet-form-submit"),
  messageForm: document.querySelector("#message-form"),
  observationForm: document.querySelector("#observation-form"),
  assistantCard: document.querySelector("#assistant-card"),
  addPetButton: document.querySelector("#add-pet-button"),
  quickAddObservation: document.querySelector("#quick-add-observation"),
  composerAddObservation: document.querySelector("#composer-add-observation"),
  closePetFormButton: document.querySelector("#close-pet-form-button"),
  editPetButton: document.querySelector("#edit-pet-button"),
  refreshButton: document.querySelector("#refresh-button"),
  workspaceBackButton: document.querySelector("#workspace-back-button"),
  modifyCarePlanButton: document.querySelector("#modify-care-plan-button"),
  careEditButtons: document.querySelectorAll("[data-care-edit]"),
  carePlanForm: document.querySelector("#care-plan-form"),
  cancelCarePlanButton: document.querySelector("#cancel-care-plan-button"),
  addRoutineRowButton: document.querySelector("#add-routine-row-button"),
  addMedicationRowButton: document.querySelector("#add-medication-row-button"),
  routineFields: document.querySelector("#routine-fields"),
  medicationFields: document.querySelector("#medication-fields"),
  routineList: document.querySelector("#routine-list"),
  medicationList: document.querySelector("#medication-list"),
  speciesInput: document.querySelector("#species"),
  breedInput: document.querySelector("#breed"),
  avatarImageInput: document.querySelector("#avatar-image"),
  avatarImagePreview: document.querySelector("#avatar-image-preview"),
  navItems: document.querySelectorAll("[data-view]"),
  viewPanels: document.querySelectorAll("[data-view-panel]"),
  petList: document.querySelector("#pet-list"),
  workspaceEyebrow: document.querySelector("#workspace-eyebrow"),
  homeTitle: document.querySelector("#home-title"),
  selectedPetTitle: document.querySelector("#selected-pet-title"),
  workspacePetAvatar: document.querySelector("#workspace-pet-avatar"),
  profileAvatar: document.querySelector("#profile-avatar"),
  profilePetName: document.querySelector("#profile-pet-name"),
  profilePetMeta: document.querySelector("#profile-pet-meta"),
  chatThread: document.querySelector("#chat-thread"),
  duplicateWarning: document.querySelector("#duplicate-warning"),
  observationsList: document.querySelector("#observations-list"),
  observationCount: document.querySelector("#observation-count"),
  connectionStatus: document.querySelector("#connection-status"),
  petCountLabel: document.querySelector("#pet-count-label"),
  summaryObservations: document.querySelector("#summary-observations"),
  summaryAlerts: document.querySelector("#summary-alerts"),
  summaryPets: document.querySelector("#summary-pets"),
  summaryWellness: document.querySelector("#summary-wellness"),
};

elements.userForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(elements.userForm);
  const displayName = textValue(form, "display_name");
  const email = textValue(form, "email");
  if (!displayName || !email) {
    showNotice("Name and email are required.");
    return;
  }
  const user = await api(`/v1/users`, {
    method: "POST",
    body: {
      display_name: displayName,
      email: email,
    },
  });
  applyWorkspaceSession(user);
  state.selectedPetId = "";
  state.observations = [];
  state.chatByPetId = {};
  state.carePlanByPetId = {};
  saveWorkspaceSession();
  await loadPets();
});

elements.navItems.forEach((item) => {
  item.addEventListener("click", () => setView(item.dataset.view));
});

elements.speciesInput.addEventListener("change", () => {
  renderBreedOptions(elements.speciesInput.value, "");
});

elements.assistantCard.addEventListener("click", () => {
  const targetPetId = state.selectedPetId || state.pets[0]?.pet_id || "";
  if (!targetPetId) {
    showNotice("Add a pet first, then open the assistant.");
    return;
  }
  selectPet(targetPetId);
});

elements.addPetButton.addEventListener("click", () => {
  if (!state.userId) {
    showNotice("Enter a workspace first.");
    return;
  }
  openPetFormForCreate();
});

elements.quickAddObservation.addEventListener("click", () => {
  openObservationForm();
});

elements.composerAddObservation.addEventListener("click", () => {
  openObservationForm();
});

elements.workspaceBackButton.addEventListener("click", () => {
  setView("home");
});

elements.modifyCarePlanButton.addEventListener("click", () => {
  openCarePlanEditor();
});

elements.careEditButtons.forEach((button) => {
  button.addEventListener("click", () => openCarePlanEditor());
});

elements.cancelCarePlanButton.addEventListener("click", () => {
  elements.carePlanForm.hidden = true;
});

elements.carePlanForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!state.selectedPetId) {
    showNotice("Choose a pet before editing a care plan.");
    return;
  }
  const form = new FormData(elements.carePlanForm);
  state.carePlanByPetId[state.selectedPetId] = carePlanFromForm(form);
  elements.carePlanForm.hidden = true;
  renderCarePlan();
});

elements.addRoutineRowButton.addEventListener("click", () => {
  addRoutineField({ label: "", value: "" });
});

elements.addMedicationRowButton.addEventListener("click", () => {
  addMedicationField({ name: "", note: "" });
});

elements.avatarImageInput.addEventListener("change", () => {
  const file = elements.avatarImageInput.files?.[0];
  if (!file) {
    state.pendingAvatarImage = "";
    elements.avatarImagePreview.textContent = "No photo selected";
    elements.avatarImagePreview.style.backgroundImage = "";
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    state.pendingAvatarImage = String(reader.result || "");
    elements.avatarImagePreview.textContent = "";
    elements.avatarImagePreview.style.backgroundImage = `url("${state.pendingAvatarImage}")`;
  });
  reader.readAsDataURL(file);
});

function openObservationForm() {
  if (!state.selectedPetId) {
    showNotice("Choose a pet first.");
    return;
  }
  elements.observationForm.reset();
  elements.duplicateWarning.hidden = true;
  state.pendingDuplicateMeal = "";
  setView("observe");
  document.querySelector("#observation-details").focus();
}

elements.editPetButton.addEventListener("click", async () => {
  if (!state.selectedPetId) {
    showNotice("Choose a pet first.");
    return;
  }
  await loadPetDetail();
  openPetFormForEdit();
});

elements.closePetFormButton.addEventListener("click", () => {
  elements.petForm.reset();
  elements.petProfilePanel.hidden = true;
});

elements.petForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.userId) {
    showNotice("Enter a user workspace first.");
    return;
  }
  const form = new FormData(elements.petForm);
  const petName = textValue(form, "name");
  if (!petName) {
    showNotice("Pet name is required.");
    return;
  }
  const petId = generatePetId(petName);
  const targetPetId = state.petFormMode === "edit" ? state.selectedPetId : petId;
  const method = state.petFormMode === "edit" ? "PATCH" : "POST";
  const path =
    state.petFormMode === "edit"
      ? `/v1/users/${encodeURIComponent(state.userId)}/pets/${encodeURIComponent(targetPetId)}`
      : `/v1/users/${encodeURIComponent(state.userId)}/pets`;
  await api(path, {
    method,
    body: {
      dog_profile: {
        id: targetPetId,
        species: textValue(form, "species") || "dog",
        name: petName,
        breed: nullableText(form, "breed"),
        age_years: nullableNumber(form, "age_years"),
        weight_kg: nullableNumber(form, "weight_kg"),
        care_notes: avatarCareNotes(form, targetPetId),
      },
      behavioral_baseline: {},
      health_baseline: {
        normal_appetite: textValue(form, "normal_appetite") || "unknown",
        normal_stool_quality: textValue(form, "normal_stool_quality") || "unknown",
        normal_activity_level: textValue(form, "normal_activity_level") || "unknown",
        known_medical_notes: linesValue(form, "known_medical_notes"),
      },
    },
  });
  elements.petForm.reset();
  elements.petProfilePanel.hidden = true;
  state.selectedPetId = targetPetId;
  await loadPets();
  await selectPet(targetPetId);
});

elements.messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.userId || !state.selectedPetId) {
    showNotice("Choose a pet before sending a message.");
    return;
  }
  const form = new FormData(elements.messageForm);
  const rawText = textValue(form, "raw_text");
  if (!rawText) {
    showNotice("Message is required.");
    return;
  }
  addChatMessage("user", rawText);
  const statusMessage = addChatMessage("assistant", "Received your update.", "working");
  try {
    const streamResult = await sendPetMessageStream(rawText, (event) => {
      updateChatMessage(statusMessage, event.message || statusLabel(event.stage), "working");
    });
    elements.messageForm.reset();
    await renderResponse(
      streamResult.response,
      rawText,
      streamResult.care_context,
      statusMessage,
    );
  } catch {
    removeChatMessage(statusMessage);
    const response = await sendPetMessage(rawText);
    elements.messageForm.reset();
    await renderResponse(response, rawText);
  }
  await loadPets();
  await loadObservations();
});

elements.observationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.userId || !state.selectedPetId) {
    showNotice("Choose a pet before saving an observation.");
    return;
  }
  const form = new FormData(elements.observationForm);
  const details = textValue(form, "details");
  if (!details) {
    showNotice("Observation details are required.");
    return;
  }
  const duplicate = duplicateMealWarning(details);
  if (duplicate && state.pendingDuplicateMeal !== duplicate) {
    state.pendingDuplicateMeal = duplicate;
    elements.duplicateWarning.textContent = duplicate;
    elements.duplicateWarning.hidden = false;
    return;
  }
  const rawText = `${details} Category: ${textValue(form, "category")}. Severity: ${textValue(form, "severity")}.`;
  addChatMessage("user", details);
  const statusMessage = addChatMessage("assistant", "Received your observation.", "working");
  try {
    const streamResult = await sendPetMessageStream(rawText, (event) => {
      updateChatMessage(statusMessage, event.message || statusLabel(event.stage), "working");
    });
    await renderResponse(
      streamResult.response,
      rawText,
      streamResult.care_context,
      statusMessage,
    );
  } catch {
    removeChatMessage(statusMessage);
    const response = await sendPetMessage(rawText);
    await renderResponse(response, rawText);
  }
  elements.observationForm.reset();
  elements.duplicateWarning.hidden = true;
  state.pendingDuplicateMeal = "";
  await loadPets();
  await loadObservations();
  setView("timeline");
});

elements.refreshButton.addEventListener("click", async () => {
  if (!state.userId) {
    return;
  }
  await loadPets();
  if (state.selectedPetId) {
    await loadObservations();
  }
});

async function loadPets() {
  const result = await api(`/v1/users/${encodeURIComponent(state.userId)}/pets`);
  state.pets = result.pets;
  updateSummary();
  if (!state.pets.some((pet) => pet.pet_id === state.selectedPetId)) {
    state.selectedPetId = "";
    state.selectedPetDetail = null;
    if (state.pets.length) {
      await selectPet(state.pets[0].pet_id);
      return;
    }
    renderSelectedPet();
    return;
  }
  renderPets();
}

async function selectPet(petId) {
  state.selectedPetId = petId;
  saveWorkspaceSession();
  await loadPetDetail();
  renderSelectedPet();
  await loadObservations();
  setView("home");
  focusComposer();
}

function applyWorkspaceSession(user) {
  state.userId = user.user_id;
  state.displayName = user.display_name || user.email || "there";
  elements.userForm.hidden = true;
  elements.petProfilePanel.hidden = true;
  elements.assistantCard.disabled = false;
  elements.addPetButton.disabled = false;
  elements.quickAddObservation.disabled = !state.selectedPetId;
  elements.refreshButton.disabled = false;
  elements.homeTitle.textContent = `Hi, ${state.displayName}`;
  elements.connectionStatus.textContent = "How is your pet doing today?";
}

function saveWorkspaceSession() {
  if (!state.userId) {
    return;
  }
  localStorage.setItem(
    workspaceStorageKey,
    JSON.stringify({
      user_id: state.userId,
      display_name: state.displayName,
      selected_pet_id: state.selectedPetId,
    }),
  );
}

async function restoreWorkspaceSession() {
  renderBreedOptions("dog", "");
  let saved = null;
  try {
    saved = JSON.parse(localStorage.getItem(workspaceStorageKey) || "null");
  } catch {
    saved = null;
  }
  if (!saved?.user_id) {
    return;
  }
  state.selectedPetId = saved.selected_pet_id || "";
  applyWorkspaceSession({
    user_id: saved.user_id,
    display_name: saved.display_name,
  });
  try {
    await loadPets();
  } catch {
    localStorage.removeItem(workspaceStorageKey);
    state.userId = "";
    state.displayName = "";
    state.selectedPetId = "";
    elements.userForm.hidden = false;
    elements.assistantCard.disabled = true;
    elements.addPetButton.disabled = true;
    elements.refreshButton.disabled = true;
  }
}

async function loadPetDetail() {
  if (!state.userId || !state.selectedPetId) {
    state.selectedPetDetail = null;
    return null;
  }
  state.selectedPetDetail = await api(
    `/v1/users/${encodeURIComponent(state.userId)}/pets/${encodeURIComponent(
      state.selectedPetId,
    )}`,
  );
  return state.selectedPetDetail;
}

async function loadObservations() {
  const result = await api(
    `/v1/users/${encodeURIComponent(state.userId)}/pets/${encodeURIComponent(
      state.selectedPetId,
    )}/observations`,
  );
  state.observations = result.observations;
  updateSummary();
  renderObservations(state.observations);
}

async function sendPetMessage(rawText) {
  return api(
    `/v1/users/${encodeURIComponent(state.userId)}/pets/${encodeURIComponent(
      state.selectedPetId,
    )}/messages`,
    {
      method: "POST",
      body: {
        raw_text: rawText,
        timestamp: new Date().toISOString(),
      },
    },
  );
}

async function sendPetMessageStream(rawText, onStatus) {
  const response = await fetch(
    `/v1/users/${encodeURIComponent(state.userId)}/pets/${encodeURIComponent(
      state.selectedPetId,
    )}/messages/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        raw_text: rawText,
        timestamp: new Date().toISOString(),
      }),
    },
  );
  if (!response.ok || !response.body) {
    throw new Error("Streaming request failed.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    blocks.forEach((block) => {
      const event = parseSseBlock(block);
      if (!event) return;
      if (event.event === "status") {
        onStatus?.(event.data || {});
      }
      if (event.event === "final") {
        finalPayload = event.data;
      }
    });
  }
  if (!finalPayload?.response) {
    throw new Error("Streaming response did not include a final message.");
  }
  return finalPayload;
}

async function fetchCareContext(rawText) {
  if (!state.userId || !state.selectedPetId || !rawText) {
    return {
      non_diagnostic_notice: "",
      professional_references: [],
      related_cases: [],
    };
  }
  return api(
    `/v1/users/${encodeURIComponent(state.userId)}/pets/${encodeURIComponent(
      state.selectedPetId,
    )}/care-context`,
    {
      method: "POST",
      body: {
        raw_text: rawText,
        limit: 3,
      },
    },
  );
}

function renderPets() {
  elements.petList.innerHTML = "";
  if (!state.pets.length) {
    const empty = document.createElement("article");
    empty.className = "empty-pets";
    empty.innerHTML = `
      <strong>No pets yet</strong>
      <span>Add a pet profile to start logging updates.</span>
    `;
    elements.petList.append(empty);
    return;
  }
  state.pets.forEach((pet) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `pet-button${pet.pet_id === state.selectedPetId ? " active" : ""}`;
    const statusClass = pet.observation_count > 0 ? "updated" : "";
    const statusText = pet.observation_count > 0 ? "Updated" : "Good";
    button.innerHTML = `
      <span class="pet-avatar ${avatarClass(pet.avatar)}" aria-hidden="true"></span>
      <span class="pet-card-body">
        <strong>${escapeHtml(pet.name || pet.pet_id)}</strong>
        <span class="pet-card-meta">${escapeHtml(speciesLabel(pet.species))} · Last check-in ${pet.observation_count ? "today" : "not yet"}</span>
        <span class="pet-status ${statusClass}">${statusText}</span>
      </span>
    `;
    setAvatarImage(button.querySelector(".pet-avatar"), pet.avatar_image);
    button.addEventListener("click", () => selectPet(pet.pet_id));
    elements.petList.append(button);
  });
}

function renderSelectedPet() {
  const pet = state.pets.find((candidate) => candidate.pet_id === state.selectedPetId);
  updateWorkspaceHeader(pet);
  elements.messageForm.hidden = !pet;
  elements.quickAddObservation.disabled = !pet;
  state.observations = [];
  if (!pet) {
    renderObservations([]);
  }
  renderPets();
  renderProfile(pet);
  renderCarePlan();
  renderChat();
}

function focusComposer() {
  if (!state.selectedPetId || elements.messageForm.hidden) {
    return;
  }
  const input = elements.messageForm.elements.raw_text;
  if (input) {
    input.focus();
  }
}

function openPetFormForCreate() {
  state.petFormMode = "create";
  elements.petForm.reset();
  state.pendingAvatarImage = "";
  elements.avatarImagePreview.textContent = "No photo selected";
  elements.avatarImagePreview.style.backgroundImage = "";
  setFormValue("species", "dog");
  renderBreedOptions("dog", "");
  elements.petFormTitle.textContent = "Add pet";
  elements.petFormSubmit.textContent = "Save profile";
  elements.petProfilePanel.hidden = false;
  document.querySelector("#pet-name").focus();
}

function openPetFormForEdit() {
  const detail = state.selectedPetDetail;
  if (!detail) {
    return;
  }
  state.petFormMode = "edit";
  state.pendingAvatarImage = avatarImageFromCareNotes(detail.dog_profile.care_notes);
  elements.avatarImagePreview.textContent = state.pendingAvatarImage ? "" : "No photo selected";
  elements.avatarImagePreview.style.backgroundImage = state.pendingAvatarImage
    ? `url("${state.pendingAvatarImage}")`
    : "";
  elements.petFormTitle.textContent = "Edit profile";
  elements.petFormSubmit.textContent = "Update profile";
  setFormValue("name", detail.dog_profile.name || "");
  setFormValue("avatar", avatarFromCareNotes(detail.dog_profile.care_notes));
  setFormValue("species", detail.dog_profile.species || "dog");
  renderBreedOptions(detail.dog_profile.species || "dog", detail.dog_profile.breed || "");
  setFormValue("age_years", String(detail.dog_profile.age_years || ""));
  setFormValue("weight_kg", String(detail.dog_profile.weight_kg || ""));
  setFormValue("normal_appetite", detail.health_baseline.normal_appetite || "unknown");
  setFormValue("normal_stool_quality", detail.health_baseline.normal_stool_quality || "unknown");
  setFormValue("normal_activity_level", detail.health_baseline.normal_activity_level || "unknown");
  setFormValue(
    "known_medical_notes",
    (detail.health_baseline.known_medical_notes || []).join("\\n"),
  );
  elements.petProfilePanel.hidden = false;
  document.querySelector("#pet-name").focus();
}

function setView(view) {
  state.currentView = view || "home";
  elements.viewPanels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.viewPanel === state.currentView);
  });
  elements.navItems.forEach((item) => {
    item.classList.toggle("active", item.dataset.view === state.currentView);
  });
  updateWorkspaceHeader(currentPet());
  if (state.currentView === "care") {
    renderCarePlan();
  }
}

function updateWorkspaceHeader(pet) {
  const titles = {
    home: pet ? pet.name || pet.pet_id : "Your pets",
    observe: "Add Observation",
    timeline: "Health Timeline",
    care: "Care Plan",
    profile: pet ? pet.name || pet.pet_id : "Profile",
  };
  const eyebrows = {
    home: pet ? "PawCare Assistant" : "Workspace",
    observe: pet ? pet.name || pet.pet_id : "Observation",
    timeline: pet ? pet.name || pet.pet_id : "Timeline",
    care: pet ? pet.name || pet.pet_id : "Care",
    profile: "Profile",
  };
  elements.workspaceEyebrow.textContent = eyebrows[state.currentView] || "Workspace";
  elements.selectedPetTitle.textContent = titles[state.currentView] || "Your pets";
  elements.workspacePetAvatar.className = `header-pet-avatar pet-avatar ${avatarClass(pet?.avatar)}`;
  setAvatarImage(elements.workspacePetAvatar, pet?.avatar_image);
  elements.workspacePetAvatar.hidden = !pet;
}

function currentPet() {
  return state.pets.find((candidate) => candidate.pet_id === state.selectedPetId);
}

async function renderResponse(
  response,
  rawText = "",
  providedCareContext = null,
  existingMessage = null,
) {
  const meta = [
    response.risk_band ? `Risk: ${response.risk_band}` : "",
    response.source_guideline_ids?.length
      ? `Guidelines: ${response.source_guideline_ids.join(", ")}`
      : "",
    response.escalation_conditions?.length
      ? `Escalation: ${response.escalation_conditions.join("; ")}`
      : "",
  ].filter(Boolean);
  const careContext = providedCareContext || await fetchCareContext(rawText);
  if (existingMessage) {
    updateChatMessage(
      existingMessage,
      response.message,
      response.status,
      meta,
      careContext,
    );
    return;
  }
  addChatMessage("assistant", response.message, response.status, meta, careContext);
}

function renderChat() {
  elements.chatThread.innerHTML = "";
  const messages = messagesForCurrentPet();
  messages.forEach((message) => appendChatBubble(message));
  elements.chatThread.scrollTop = elements.chatThread.scrollHeight;
}

function renderObservations(observations) {
  elements.observationCount.textContent = String(observations.length);
  elements.observationsList.innerHTML = "";
  if (!observations.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = state.selectedPetId ? "No observations recorded." : "No pet selected.";
    elements.observationsList.append(empty);
    return;
  }
  const grouped = groupObservationsByDay(observations.slice().reverse());
  grouped.forEach(({ label, items }) => {
    const day = document.createElement("section");
    day.className = "timeline-day";
    day.innerHTML = `<h4>${escapeHtml(label)}</h4>`;
    items.forEach((observation) => {
      const entry = document.createElement("div");
      entry.className = "timeline-entry";
      const item = document.createElement("article");
      item.className = "observation-item";
      item.innerHTML = `
        <div class="observation-item-header">
          <strong>${labelForCategory(observation.category)}</strong>
          <span>${escapeHtml(timeLabel(observation.timestamp))}</span>
        </div>
        <p>${escapeHtml(observation.raw_text || "")}</p>
        <span class="pet-status ${statusClassForObservation(observation)}">${statusTextForObservation(observation)}</span>
      `;
      entry.innerHTML = `
        <time class="timeline-time">${escapeHtml(timeLabel(observation.timestamp))}</time>
        <span class="timeline-dot" aria-hidden="true">${dotLabel(observation.category)}</span>
      `;
      entry.append(item);
      day.append(entry);
    });
    elements.observationsList.append(day);
  });
}

function renderProfile(pet) {
  elements.profileAvatar.textContent = "";
  elements.profileAvatar.className = `profile-avatar ${avatarClass(pet?.avatar)}`;
  setAvatarImage(elements.profileAvatar, pet?.avatar_image);
  elements.profilePetName.textContent = pet ? pet.name || pet.pet_id : "No pet selected";
  elements.profilePetMeta.textContent = pet
    ? `${speciesLabel(pet.species)} · ${pet.observation_count} observations`
    : "Choose a pet from Home.";
}

function renderBreedOptions(species, selectedBreed = "") {
  const optionsBySpecies = {
    dog: [
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
    ],
    cat: [
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
    ],
  };
  const options = optionsBySpecies[species] || optionsBySpecies.dog;
  elements.breedInput.innerHTML = options
    .map(
      ([value, label]) =>
        `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`,
    )
    .join("");
  elements.breedInput.value = selectedBreed;
}

function speciesLabel(species) {
  return species === "cat" ? "Cat" : "Dog";
}

function renderCarePlan() {
  const plan = carePlanForCurrentPet();
  elements.routineList.innerHTML = "";
  plan.routines.forEach((routine, index) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <span class="${index === 0 ? "done" : ""}"></span>
      <strong>${escapeHtml(routine.label)}</strong>
      <time>${escapeHtml(formatCareValue(routine.value))}</time>
    `;
    elements.routineList.append(item);
  });
  elements.medicationList.innerHTML = "";
  plan.medications.forEach((medication) => {
    const item = document.createElement("div");
    item.className = "medication-row";
    item.innerHTML = `
      <span class="medicine-dot"></span>
      <div>
        <strong>${escapeHtml(medication.name)}</strong>
        <p>${escapeHtml(medication.note)}</p>
      </div>
    `;
    elements.medicationList.append(item);
  });
}

function openCarePlanEditor() {
  if (!state.selectedPetId) {
    showNotice("Choose a pet before editing a care plan.");
    return;
  }
  const plan = carePlanForCurrentPet();
  const byLabel = Object.fromEntries(plan.routines.map((routine) => [routine.label, routine.value]));
  setCarePlanFormValue("breakfast_time", byLabel.Breakfast || "07:00");
  setCarePlanFormValue("walk_time", byLabel["Morning walk"] || "08:00");
  setCarePlanFormValue("afternoon_activity", byLabel["Afternoon activity"] || "Play time at 4:00 PM");
  setCarePlanFormValue("potty_interval", byLabel["Potty time"] || "Every 3 hours");
  setCarePlanFormValue("potty_bedtime", byLabel["Potty before bed"] || "21:30");
  setCarePlanFormValue("treat_count", byLabel["Treat time"] || "2-3 times");
  setCarePlanFormValue("dinner_time", byLabel.Dinner || "19:00");
  elements.routineFields.innerHTML = "";
  plan.routines
    .filter((routine) => !defaultRoutineLabels().includes(routine.label))
    .forEach((routine) => addRoutineField(routine));
  elements.medicationFields.innerHTML = "";
  plan.medications.forEach((medication) => addMedicationField(medication));
  elements.carePlanForm.hidden = false;
  elements.carePlanForm.scrollIntoView({ block: "nearest" });
}

function carePlanForCurrentPet() {
  const key = state.selectedPetId || "_system";
  if (!state.carePlanByPetId[key]) {
    state.carePlanByPetId[key] = {
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
  return state.carePlanByPetId[key];
}

function carePlanFromForm(form) {
  const routines = [
    { label: "Breakfast", value: textValue(form, "breakfast_time") || "07:00" },
    { label: "Morning walk", value: textValue(form, "walk_time") || "08:00" },
    {
      label: "Afternoon activity",
      value: textValue(form, "afternoon_activity") || "Play time at 4:00 PM",
    },
    { label: "Potty time", value: textValue(form, "potty_interval") || "Every 3 hours" },
    { label: "Potty before bed", value: textValue(form, "potty_bedtime") || "21:30" },
    { label: "Treat time", value: textValue(form, "treat_count") || "2-3 times" },
    { label: "Dinner", value: textValue(form, "dinner_time") || "19:00" },
  ];
  routines.push(...readDynamicRows(elements.routineFields, "routine"));
  const medications = readDynamicRows(elements.medicationFields, "medication");
  if (!medications.length) {
    medications.push({ name: "Probiotic", note: "Every morning after breakfast" });
  }
  return { routines, medications };
}

function addRoutineField(routine) {
  const row = document.createElement("div");
  row.className = "dynamic-row";
  row.innerHTML = `
    <input name="routine_label" placeholder="Routine name" value="${escapeHtml(routine.label)}" />
    <input name="routine_value" placeholder="Time or frequency" value="${escapeHtml(routine.value)}" />
    <button class="secondary-button remove-row-button" type="button">Remove</button>
  `;
  row.querySelector("button").addEventListener("click", () => row.remove());
  elements.routineFields.append(row);
}

function addMedicationField(medication) {
  const row = document.createElement("div");
  row.className = "dynamic-row medication-edit-row";
  row.innerHTML = `
    <input name="medication_name" placeholder="Medication name" value="${escapeHtml(medication.name)}" />
    <input name="medication_note" placeholder="When / how often" value="${escapeHtml(medication.note)}" />
    <button class="secondary-button remove-row-button" type="button">Remove</button>
  `;
  row.querySelector("button").addEventListener("click", () => row.remove());
  elements.medicationFields.append(row);
}

function readDynamicRows(container, type) {
  return Array.from(container.querySelectorAll(".dynamic-row"))
    .map((row) => {
      if (type === "routine") {
        return {
          label: String(row.querySelector("[name='routine_label']")?.value || "").trim(),
          value: String(row.querySelector("[name='routine_value']")?.value || "").trim(),
        };
      }
      return {
        name: String(row.querySelector("[name='medication_name']")?.value || "").trim(),
        note: String(row.querySelector("[name='medication_note']")?.value || "").trim(),
      };
    })
    .filter((item) => {
      if ("label" in item) return item.label && item.value;
      return item.name && item.note;
    });
}

function defaultRoutineLabels() {
  return [
    "Breakfast",
    "Morning walk",
    "Afternoon activity",
    "Potty time",
    "Potty before bed",
    "Treat time",
    "Dinner",
  ];
}

function setCarePlanFormValue(name, value) {
  const field = elements.carePlanForm.elements[name];
  if (field) {
    field.value = value;
  }
}

function formatTime(value) {
  if (!value || !value.includes(":")) {
    return value || "--";
  }
  const [hoursRaw, minutes] = value.split(":");
  const hours = Number(hoursRaw);
  if (Number.isNaN(hours)) {
    return value;
  }
  const suffix = hours >= 12 ? "PM" : "AM";
  const displayHour = hours % 12 || 12;
  return `${displayHour}:${minutes} ${suffix}`;
}

function formatCareValue(value) {
  if (String(value || "").match(/^\\d{2}:\\d{2}$/)) {
    return formatTime(value);
  }
  return value || "--";
}

function setFormValue(name, value) {
  const field = elements.petForm.elements[name];
  if (!field) {
    return;
  }
  if (field instanceof RadioNodeList) {
    field.value = value || "collie";
    return;
  }
  field.value = value;
}

function avatarFromCareNotes(notes) {
  const note = (notes || []).find((candidate) => candidate.startsWith("avatar:"));
  return note ? note.replace("avatar:", "") : "collie";
}

function avatarImageFromCareNotes(notes) {
  const note = (notes || []).find((candidate) => candidate.startsWith("avatar_image:"));
  return note ? note.replace("avatar_image:", "") : "";
}

function avatarCareNotes(form, targetPetId) {
  const notes = [`avatar:${textValue(form, "avatar") || "collie"}`];
  const image =
    state.pendingAvatarImage ||
    avatarImageFromCareNotes(state.selectedPetDetail?.dog_profile?.care_notes || []);
  if (image && targetPetId === state.selectedPetId) {
    notes.push(`avatar_image:${image}`);
  } else if (image && state.petFormMode === "create") {
    notes.push(`avatar_image:${image}`);
  }
  return notes;
}

function setAvatarImage(element, image) {
  if (!element) {
    return;
  }
  if (image) {
    element.classList.add("has-image");
    element.style.backgroundImage = `url("${image}")`;
  } else {
    element.classList.remove("has-image");
    element.style.backgroundImage = "";
  }
}

function updateSummary() {
  const observationTotal = state.pets.reduce((total, pet) => total + pet.observation_count, 0);
  const alertTotal = state.observations.filter((observation) =>
    ["vomiting", "stool", "medication_note", "mobility"].includes(observation.category),
  ).length;
  elements.petCountLabel.textContent = String(state.pets.length);
  elements.summaryObservations.textContent = String(observationTotal);
  elements.summaryAlerts.textContent = String(alertTotal);
  elements.summaryPets.textContent = String(state.pets.length);
  elements.summaryWellness.textContent = state.pets.length ? "92%" : "--";
}

function labelForCategory(category) {
  return String(category || "observation")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function groupObservationsByDay(observations) {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const todayKey = dateKey(today);
  const yesterdayKey = dateKey(yesterday);
  const groups = [];
  observations.forEach((observation) => {
    const key = String(observation.timestamp || "").slice(0, 10) || "unknown";
    let label = key;
    if (key === todayKey) label = "Today";
    if (key === yesterdayKey) label = "Yesterday";
    let group = groups.find((candidate) => candidate.label === label);
    if (!group) {
      group = { label, items: [] };
      groups.push(group);
    }
    group.items.push(observation);
  });
  return groups;
}

function dateKey(date) {
  return date.toISOString().slice(0, 10);
}

function timeLabel(timestamp) {
  const date = new Date(timestamp || "");
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function dotLabel(category) {
  if (category === "stool") return "S";
  if (category === "vomiting") return "V";
  if (category === "energy") return "E";
  if (category === "food_intake" || category === "appetite") return "A";
  return "O";
}

function statusTextForObservation(observation) {
  const rawText = String(observation.raw_text || "").toLowerCase();
  if (rawText.includes("bloody") || rawText.includes("black") || rawText.includes("vomit")) {
    return "Attention Needed";
  }
  if (rawText.includes("less") || rawText.includes("low") || rawText.includes("tired")) {
    return "Monitoring";
  }
  return "Good";
}

function statusClassForObservation(observation) {
  const status = statusTextForObservation(observation);
  if (status === "Attention Needed") return "updated";
  if (status === "Monitoring") return "monitoring";
  return "";
}

function initialFor(value) {
  return String(value || "P").trim().charAt(0).toUpperCase() || "P";
}

function avatarClass(avatar) {
  const allowed = ["collie", "golden", "black", "cat"];
  return `avatar-${allowed.includes(avatar) ? avatar : "collie"}`;
}

function showNotice(message) {
  addChatMessage("assistant", message, "notice", []);
}

function addChatMessage(
  role,
  message,
  status = "",
  meta = [],
  careContext = null,
) {
  const chat = messagesForCurrentPet();
  const chatMessage = { role, message, status, meta, careContext };
  chat.push(chatMessage);
  appendChatBubble(chatMessage);
  elements.chatThread.scrollTop = elements.chatThread.scrollHeight;
  return chatMessage;
}

function updateChatMessage(
  chatMessage,
  message,
  status = chatMessage.status,
  meta = chatMessage.meta || [],
  careContext = chatMessage.careContext || null,
) {
  chatMessage.message = message;
  chatMessage.status = status;
  chatMessage.meta = meta;
  chatMessage.careContext = careContext;
  renderChat();
}

function removeChatMessage(chatMessage) {
  const chat = messagesForCurrentPet();
  const index = chat.indexOf(chatMessage);
  if (index >= 0) {
    chat.splice(index, 1);
    renderChat();
  }
}

function messagesForCurrentPet() {
  const key = state.selectedPetId || "_system";
  if (!state.chatByPetId[key]) {
    const pet = currentPet();
    state.chatByPetId[key] = [
      {
        role: "assistant",
        message: pet
          ? `You're chatting about ${pet.name || pet.pet_id}. Tell me meals, stool, energy, vomiting, behavior, or any care question.`
          : "Choose a pet, then tell me what happened.",
        status: "",
        meta: [],
      },
    ];
  }
  return state.chatByPetId[key];
}

function appendChatBubble({
  role,
  message,
  status = "",
  meta = [],
  careContext = null,
}) {
  const item = document.createElement("article");
  item.className = `chat-bubble ${role}`;
  if (role === "assistant") {
    item.innerHTML = `
      <div class="assistant-avatar" aria-hidden="true">🤖</div>
      <div>
        <strong>PawCare Assistant</strong>
        ${status ? `<span class="status-pill ${escapeHtml(status)}">${escapeHtml(status)}</span>` : ""}
        <p>${escapeHtml(message)}</p>
        ${meta.length ? `<ul>${meta.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}</ul>` : ""}
        ${renderCareContextMarkup(careContext)}
      </div>
    `;
  } else {
    item.innerHTML = `<p>${escapeHtml(message)}</p>`;
  }
  elements.chatThread.append(item);
}

function parseSseBlock(block) {
  const lines = String(block || "").split("\n");
  let event = "message";
  const dataLines = [];
  lines.forEach((line) => {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  });
  if (!dataLines.length) {
    return null;
  }
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

function statusLabel(stage) {
  const labels = {
    received: "Received your update.",
    loading_pet: "Loading pet workspace.",
    processing_message: "Checking health and behavior signals.",
    retrieving_care_context: "Retrieving care context.",
    safety_review: "Final safety review complete.",
  };
  return labels[stage] || "Working on this update.";
}

function renderCareContextMarkup(careContext = null) {
  const references = careContext?.professional_references || [];
  const relatedCases = careContext?.related_cases || [];
  const notice = careContext?.non_diagnostic_notice || "";
  const contextSummary = careContext?.context_summary || "";
  if (!contextSummary && !references.length && !relatedCases.length) {
    return "";
  }
  return `
    <section class="related-cases" aria-label="Care context">
      <div class="related-cases-header">
        <strong>Care context</strong>
        <span>Not a diagnosis</span>
      </div>
      ${notice ? `<p class="case-disclaimer">${escapeHtml(notice)}</p>` : ""}
      ${contextSummary ? `<p class="context-summary">${escapeHtml(contextSummary)}</p>` : ""}
      <div class="case-card-list">
        ${references.map((item) => renderProfessionalReferenceCard(item)).join("")}
        ${relatedCases.map((item) => renderRelatedCaseCard(item)).join("")}
      </div>
    </section>
  `;
}

function renderProfessionalReferenceCard(item) {
  const redFlags = item.red_flags || [];
  const record = item.what_to_record || [];
  const topics = item.vet_discussion_topics || [];
  return `
    <article class="case-card professional-reference-card">
      <div class="case-card-topline">
        <span>Vet reference</span>
        <span>${escapeHtml(item.relevance_level || "related")}</span>
      </div>
      <h4>${escapeHtml(item.source_name || "Professional reference")}</h4>
      <p>${escapeHtml(item.summary || "")}</p>
      ${topics.length ? `<p><strong>Discuss with vet:</strong> ${escapeHtml(topics.slice(0, 4).join(", "))}</p>` : ""}
      ${record.length ? `<p><strong>Record before visit:</strong> ${escapeHtml(record.slice(0, 5).join(", "))}</p>` : ""}
      ${redFlags.length ? `<p><strong>Watch urgently for:</strong> ${escapeHtml(redFlags.slice(0, 3).join("; "))}</p>` : ""}
      <a href="${escapeAttribute(item.source_url || "#")}" target="_blank" rel="noopener noreferrer">
        Open reference
      </a>
    </article>
  `;
}

function renderRelatedCaseCard(item) {
  const topics = item.possible_discussion_topics || [];
  const redFlags = item.red_flags || [];
  const symptoms = item.matched_symptoms || [];
  return `
    <article class="case-card">
      <div class="case-card-topline">
        <span>Similar case</span>
        <span>${escapeHtml(item.condition_discussion_priority || "discussion topic")}</span>
      </div>
      <h4>${escapeHtml(item.title || "Related pet case")}</h4>
      <p>${escapeHtml(item.case_summary || "")}</p>
      ${symptoms.length ? `<p><strong>Matched signs:</strong> ${escapeHtml(symptoms.join(", "))}</p>` : ""}
      ${topics.length ? `<p><strong>Vet discussion topics:</strong> ${escapeHtml(topics.join(", "))}</p>` : ""}
      ${redFlags.length ? `<p><strong>Watch urgently for:</strong> ${escapeHtml(redFlags.slice(0, 3).join("; "))}</p>` : ""}
      <a href="${escapeAttribute(item.source_url || "#")}" target="_blank" rel="noopener noreferrer">
        Open original source
      </a>
    </article>
  `;
}

function duplicateMealWarning(details) {
  const meal = mealKeyword(details);
  if (!meal) {
    return "";
  }
  const today = new Date().toISOString().slice(0, 10);
  const duplicate = state.observations.some((observation) => {
    const timestamp = String(observation.timestamp || "");
    const rawText = String(observation.raw_text || "");
    return timestamp.startsWith(today) && mealKeyword(rawText) === meal;
  });
  return duplicate
    ? `There is already a ${meal} observation for today. Save again if this is a separate update.`
    : "";
}

function mealKeyword(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized.includes("breakfast")) return "breakfast";
  if (normalized.includes("lunch")) return "lunch";
  if (normalized.includes("dinner")) return "dinner";
  return "";
}

async function api(path, options = {}) {
  const fetchOptions = {
    method: options.method || "GET",
    headers: {},
  };
  if (options.body) {
    fetchOptions.headers["Content-Type"] = "application/json";
    fetchOptions.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, fetchOptions);
  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Request failed.";
    showNotice(detail);
    throw new Error(detail);
  }
  return data;
}

function textValue(form, key) {
  return String(form.get(key) || "").trim();
}

function nullableText(form, key) {
  return textValue(form, key) || null;
}

function nullableNumber(form, key) {
  const value = textValue(form, key);
  return value ? Number(value) : null;
}

function linesValue(form, key) {
  return textValue(form, key)
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function generatePetId(name) {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 32);
  const suffix = Date.now().toString(36);
  return `dog_${slug || "pet"}_${suffix}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  const candidate = String(value || "");
  if (!candidate.startsWith("https://") && !candidate.startsWith("http://")) {
    return "#";
  }
  return escapeHtml(candidate);
}

restoreWorkspaceSession();
