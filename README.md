# Wiki-Search

A mini-project to form an efficient index of Wikipedia articles for search queries

## Phase 1

- Data can be downloaded from [here](https://drive.google.com/file/d/1tknEB9yt2AXNKJp3UvJoNRyfiTh-Nzpr) [ 350MB ]
- Only indexing will be evaluated in Phase 1
- The index size should be at max a quarter of the dump size
- Keep in mind that field queries have to be implemented in Phase 2:
    - Title
    - Body Text
    - <u>InfoBox</u> [ Give more relevance ]
    - Categories
    - <u>External Links (outlinks)</u> [ Code-mixed data will be tested through external links, also take care in tokenisation ]
    - References
- Inverted index has to be created

### Indexing

- Steps involved in indexing are:
    1. Parsing
    2. Tokenisation
    3. Case Folding
    4. Stop Words Removal
    5. Stemming:
        1. Allowed libs: `pystemmer, nltk (PorterStemmer, SnowballStemmer, WordNetLemmatizer), spacy`
    6. Inverted Index creation

## Phase 2

- Inverted index creation on the whole English Wikipedia dump
- Implement ranking mechanism for results
- Have an end-to-end search system
