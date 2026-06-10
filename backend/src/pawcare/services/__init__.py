from pawcare.services.case_models import (
    BehaviorCareReference,
    BehaviorReferenceMatch,
    CaseMatch,
    CommunityCase,
    KnowledgeMatch,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeRecord,
    ProfessionalCareReference,
    ProfessionalReferenceMatch,
)
from pawcare.services.behavior_reference_service import BehaviorReferenceService
from pawcare.services.knowledge_index import KnowledgeIndex, LocalKnowledgeIndex
from pawcare.services.knowledge_fts_index import (
    KnowledgeChunker,
    SQLiteKnowledgeFTSIndex,
    seed_professional_knowledge_documents,
)
from pawcare.services.knowledge_pack_loader import KnowledgePackLoader
from pawcare.services.knowledge_summarizer import (
    DeterministicKnowledgeSummarizer,
    KnowledgeSummarizer,
    OpenAIKnowledgeSummarizer,
    build_knowledge_summarizer,
)
from pawcare.services.llm_signal_screening_service import (
    DeterministicLLMSignalScreeningService,
    LLMSignalScreeningResult,
    LLMSignalScreeningService,
    OpenAILLMSignalScreeningService,
    build_llm_signal_screening_service,
)
from pawcare.services.llm_usage import (
    LLMUsageCollector,
    LLMUsageRecord,
    extract_openai_usage_record,
    summarize_usage,
)
from pawcare.services.in_memory_pet_repository import InMemoryPetRepository
from pawcare.services.pet_models import (
    CareRoutine,
    DailyPetSummary,
    DogContextSnapshot,
    MonitoringAlert,
    MonthlyPetSummary,
    PetRecord,
    UserAccount,
    WeeklyPetSummary,
)
from pawcare.services.pet_repository import PetRecordAccessError, PetRepository
from pawcare.services.pet_summary_worker import SummaryWorker
from pawcare.services.professional_reference_service import ProfessionalReferenceService
from pawcare.services.response_polisher import (
    DeterministicResponsePolisher,
    OpenAIResponsePolisher,
    ResponsePolisher,
    build_response_polisher,
)
from pawcare.services.semantic_care_context_cache import (
    SemanticCareContextCache,
    SemanticCareContextCacheKey,
    SemanticCareContextCacheLookup,
)
from pawcare.services.similar_case_service import SimilarCaseService
from pawcare.storage import SQLitePetRepository


def __getattr__(name: str) -> object:
    if name in {"LogProcessingResult", "LogProcessingService"}:
        from pawcare.services.log_processing_service import (
            LogProcessingResult,
            LogProcessingService,
        )

        return {
            "LogProcessingResult": LogProcessingResult,
            "LogProcessingService": LogProcessingService,
        }[name]
    if name == "PetMessageService":
        from pawcare.services.pet_message_service import PetMessageService

        return PetMessageService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CaseMatch",
    "BehaviorCareReference",
    "BehaviorReferenceMatch",
    "BehaviorReferenceService",
    "CareRoutine",
    "CommunityCase",
    "DailyPetSummary",
    "DogContextSnapshot",
    "InMemoryPetRepository",
    "KnowledgeIndex",
    "KnowledgeChunk",
    "KnowledgeChunker",
    "KnowledgeDocument",
    "KnowledgeMatch",
    "KnowledgePackLoader",
    "KnowledgeRecord",
    "KnowledgeSummarizer",
    "LocalKnowledgeIndex",
    "LogProcessingResult",
    "LogProcessingService",
    "MonitoringAlert",
    "MonthlyPetSummary",
    "OpenAIKnowledgeSummarizer",
    "PetMessageService",
    "PetRecord",
    "PetRecordAccessError",
    "PetRepository",
    "ProfessionalCareReference",
    "ProfessionalReferenceMatch",
    "ProfessionalReferenceService",
    "SQLitePetRepository",
    "SQLiteKnowledgeFTSIndex",
    "SemanticCareContextCache",
    "SemanticCareContextCacheKey",
    "SemanticCareContextCacheLookup",
    "SimilarCaseService",
    "SummaryWorker",
    "UserAccount",
    "WeeklyPetSummary",
    "DeterministicKnowledgeSummarizer",
    "DeterministicLLMSignalScreeningService",
    "DeterministicResponsePolisher",
    "LLMSignalScreeningResult",
    "LLMSignalScreeningService",
    "LLMUsageCollector",
    "LLMUsageRecord",
    "OpenAIResponsePolisher",
    "ResponsePolisher",
    "build_knowledge_summarizer",
    "OpenAILLMSignalScreeningService",
    "build_llm_signal_screening_service",
    "build_response_polisher",
    "extract_openai_usage_record",
    "seed_professional_knowledge_documents",
    "summarize_usage",
]
