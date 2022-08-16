# Wiki-Search

A mini-project to form an efficient index of Wikipedia articles for search queries

## Phase 1

### Implemented

- Indexer:
    - contains vocabulary file
    - contains article id to title mapping
    - contains inverted index broken into files by field type

### Not Implemented

- Searching for articles

### Running

- The indexer can be run as follows:
    - `bash index.sh <path_to_dump> <dir_to_inverted_index> <path_to_stats_file>`

### Requirements

- PyStemmer
