"""
P28: Personal Research Library

Full-stack personal research library management:
- Zotero import via CSL/BibTeX/Zotero API
- LLM-based auto-tagging with topic classification
- Smart collections based on research themes
- PDF annotation viewer with highlights and notes
- Reading list management (to-read, reading, completed)
"""

from research_agent.personal_library.models import (
    LibraryEntry,
    LibraryEntryStatus,
    SmartCollection,
    ReadingListStatus,
    Annotation as AnnotationModel,
    TagSuggestion,
    ZoteroImportResult,
    LibraryStats,
    LibraryItem,
    Collection,
    CollectionRule,
    MatchOperator,
)
from research_agent.personal_library.library import PersonalLibrary
from research_agent.personal_library.zotero import ZoteroImporter, import_from_bibtex, import_from_zotero_json
from research_agent.personal_library.tagger import AutoTagger, auto_tag_item, get_suggested_tags
from research_agent.personal_library.collections import (
    list_collections,
    get_collection,
    create_collection,
    update_collection,
    delete_collection,
    add_item_to_collection,
    remove_item_from_collection,
    auto_assign_collections,
)
from research_agent.personal_library.annotation import (
    Annotation,
    AnnotationRegion,
    create_annotation,
    list_annotations,
    update_annotation,
    delete_annotation,
)
from research_agent.personal_library.reading_list import (
    ReadingListItem,
    ReadingPriority,
    ReadingStatus,
    add_to_reading_list,
    list_reading_list,
    update_reading_entry,
    remove_from_reading_list,
    reading_list_stats,
)

__all__ = [
    "LibraryEntry",
    "LibraryEntryStatus",
    "SmartCollection",
    "ReadingListStatus",
    "AnnotationModel",
    "Annotation",
    "AnnotationRegion",
    "TagSuggestion",
    "ZoteroImportResult",
    "LibraryStats",
    "LibraryItem",
    "Collection",
    "CollectionRule",
    "MatchOperator",
    "PersonalLibrary",
    "ZoteroImporter",
    "AutoTagger",
    "import_from_bibtex",
    "import_from_zotero_json",
    "auto_tag_item",
    "get_suggested_tags",
    "list_collections",
    "get_collection",
    "create_collection",
    "update_collection",
    "delete_collection",
    "add_item_to_collection",
    "remove_item_from_collection",
    "auto_assign_collections",
    "create_annotation",
    "list_annotations",
    "update_annotation",
    "delete_annotation",
    "ReadingListItem",
    "ReadingPriority",
    "ReadingStatus",
    "add_to_reading_list",
    "list_reading_list",
    "update_reading_entry",
    "remove_from_reading_list",
    "reading_list_stats",
]
