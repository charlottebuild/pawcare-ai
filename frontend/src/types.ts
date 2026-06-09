export type View = "home" | "observe" | "timeline" | "care" | "profile";

export type UserAccount = {
  user_id: string;
  display_name?: string | null;
  email?: string | null;
};

export type PetSummary = {
  pet_id: string;
  name: string;
  species: string;
  avatar?: string | null;
  avatar_image?: string | null;
  observation_count: number;
};

export type PetDetail = {
  pet_id: string;
  user_id: string;
  dog_profile: {
    id: string;
    name: string;
    species?: string | null;
    breed?: string | null;
    age_years?: number | null;
    weight_kg?: number | null;
    care_notes?: string[];
  };
  health_baseline: {
    normal_appetite?: string | null;
    normal_stool_quality?: string | null;
    normal_activity_level?: string | null;
    known_medical_notes?: string[];
  };
  behavioral_baseline: Record<string, unknown>;
  observation_count: number;
};

export type Observation = {
  observation_id: string;
  timestamp: string;
  category: string;
  raw_text: string;
  health_context?: Record<string, unknown>;
};

export type UserResponse = {
  status: string;
  message: string;
  risk_band?: string | null;
  source_guideline_ids?: string[];
  escalation_conditions?: string[];
};

export type CareContext = {
  non_diagnostic_notice?: string;
  context_summary?: string;
  professional_references?: ProfessionalReference[];
  related_cases?: RelatedCase[];
  cache_status?: string;
};

export type ProfessionalReference = {
  source_name?: string;
  source_url?: string;
  summary?: string;
  relevance_level?: string;
  vet_discussion_topics?: string[];
  what_to_record?: string[];
  red_flags?: string[];
};

export type RelatedCase = {
  title?: string;
  source_url?: string;
  case_summary?: string;
  condition_discussion_priority?: string;
  matched_symptoms?: string[];
  possible_discussion_topics?: string[];
  red_flags?: string[];
};

export type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  message: string;
  status?: string;
  meta?: string[];
  careContext?: CareContext | null;
};

export type Routine = {
  label: string;
  value: string;
};

export type Medication = {
  name: string;
  note: string;
};

export type CarePlan = {
  routines: Routine[];
  medications: Medication[];
};
