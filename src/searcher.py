from collections import defaultdict
import os
import sys
import time
import re
import bisect
import heapq
import string

# Stemmer <<<
from Stemmer import Stemmer

ENGLISH_STEMMER = Stemmer("english")
ENGLISH_STOPWORDS = {
    "or",
    "re",
    "needn",
    "hadn",
    "have",
    "than",
    "i",
    "again",
    "just",
    "dont",
    "wasnt",
    "some",
    "dure",
    "that",
    "a",
    "few",
    "other",
    "mightnt",
    "wont",
    "couldn",
    "you",
    "myself",
    "how",
    "your",
    "don",
    "neednt",
    "now",
    "so",
    "wouldn",
    "most",
    "be",
    "an",
    "ourselv",
    "there",
    "through",
    "are",
    "arent",
    "here",
    "werent",
    "ll",
    "further",
    "onc",
    "both",
    "am",
    "won",
    "haven",
    "hasnt",
    "into",
    "on",
    "they",
    "veri",
    "shouldnt",
    "at",
    "against",
    "youd",
    "down",
    "but",
    "becaus",
    "m",
    "should",
    "all",
    "where",
    "she",
    "thatll",
    "abov",
    "did",
    "shouldv",
    "yourself",
    "whom",
    "nor",
    "same",
    "off",
    "those",
    "to",
    "if",
    "ani",
    "which",
    "shouldn",
    "below",
    "whi",
    "between",
    "the",
    "doesnt",
    "onli",
    "themselv",
    "more",
    "has",
    "their",
    "aren",
    "itself",
    "will",
    "mustn",
    "our",
    "herself",
    "himself",
    "he",
    "under",
    "my",
    "from",
    "havent",
    "youv",
    "shes",
    "out",
    "over",
    "ma",
    "couldnt",
    "for",
    "who",
    "too",
    "while",
    "what",
    "this",
    "no",
    "me",
    "s",
    "d",
    "yourselv",
    "about",
    "her",
    "mustnt",
    "own",
    "can",
    "then",
    "mightn",
    "o",
    "such",
    "wasn",
    "when",
    "shant",
    "shan",
    "hasn",
    "t",
    "these",
    "were",
    "do",
    "befor",
    "isnt",
    "weren",
    "of",
    "and",
    "his",
    "was",
    "didnt",
    "youll",
    "ain",
    "not",
    "isn",
    "by",
    "after",
    "with",
    "we",
    "it",
    "ve",
    "had",
    "is",
    "them",
    "up",
    "didn",
    "as",
    "in",
    "him",
    "hadnt",
    "wouldnt",
    "been",
    "doesn",
    "each",
    "until",
    "y",
    "doe",
}
# >>>

# Base Conversion <<<
ENCODING_CHARS = "".join(
    ["!+", string.digits, string.ascii_uppercase, string.ascii_lowercase]
)
ENCODING_CHAR_TO_INDEX = dict(
    (char, indx) for (indx, char) in enumerate(ENCODING_CHARS)
)
ENCODING_BASE = len(ENCODING_CHARS)


def base_64_encode(num):
    chars = []
    while True:
        num, rem = divmod(num, ENCODING_BASE)
        chars.append(ENCODING_CHARS[rem])
        if num == 0:
            break

    chars = list(reversed(chars))
    return "".join(chars)


def base_64_decode(chars):
    num = 0
    for char in chars:
        num = num * ENCODING_BASE + ENCODING_CHAR_TO_INDEX[char]
    return num


# >>>

# Utils <<<
def normalize_enc_doc_id(enc_doc_id):
    zeros_required = 8 - len(enc_doc_id)
    return f"{zeros_required*ENCODING_CHARS[0]}{enc_doc_id}"


def process_query(query):

    query = query.encode("ascii", errors="ignore").decode()

    for sym in {
        "&nbsp;",
        "&lt;",
        "&gt;",
        "&amp;",
        "&quot;",
        "&apos;",
        "—",
        "%",
        "$",
        "'",
        "~",
        "|",
        ".",
        "*",
        "[",
        "]",
        ":",
        ";",
        ",",
        "{",
        "}",
        "(",
        ")",
        "=",
        "+",
        "-",
        "_",
        "#",
        "!",
        "`",
        '"',
        "?",
        "/",
        ">",
        "<",
        "&",
        "\\",
    }:
        query = query.replace(sym, " ")

    query = query.split()

    query = ENGLISH_STEMMER.stemWords(query)
    query = [
        token
        for token in query
        if (
            (token.isalpha())
            and (token not in ENGLISH_STOPWORDS)
            and (3 < len(token) < 15)
        )
        or (token.isnumeric() and len(token) <= 7)
    ]

    return query


# >>>

# Constants <<<
FIELD_TYPE_TITLE = "t"
FIELD_TYPE_BODY = "b"
FIELD_TYPE_INFOBOX = "i"
FIELD_TYPE_CATEGORIES = "c"
FIELD_TYPE_EXTERNAL_LINKS = "l"
FIELD_TYPE_REFERENCES = "r"
# >>>

# Configuration <<<
FIELD_TYPE_TO_WEIGHT_MAP_FIELD_QUERY = {
    FIELD_TYPE_TITLE: 55,
    FIELD_TYPE_BODY: 1.0,
    FIELD_TYPE_INFOBOX: 20,
    FIELD_TYPE_CATEGORIES: 15,
    FIELD_TYPE_EXTERNAL_LINKS: 15,
    FIELD_TYPE_REFERENCES: 15,
}
FIELD_TYPE_TO_WEIGHT_MAP_NORMAL_QUERY = {
    FIELD_TYPE_TITLE: 45,
    FIELD_TYPE_BODY: 0.3,
    FIELD_TYPE_INFOBOX: 10,
    FIELD_TYPE_CATEGORIES: 0.2,
    FIELD_TYPE_EXTERNAL_LINKS: 0.1,
    FIELD_TYPE_REFERENCES: 0.1,
}
NUM_RESULTS_PER_QUERY = 10
# >>>

# File Name Queries <<<
FIELD_TO_DOCUMENT_HEADINGS_MAP = {}


def get_document_headings(field_type):
    global FIELD_TO_DOCUMENT_HEADINGS_MAP

    file_name = os.path.join(index_dir, f"preindex_{field_type}")
    with open(file_name, "r") as f:
        data = f.readlines()
        FIELD_TO_DOCUMENT_HEADINGS_MAP[field_type] = [line.strip() for line in data]


def get_file_num_for_query(field_type, query):

    num = bisect.bisect_left(FIELD_TO_DOCUMENT_HEADINGS_MAP[field_type], query)
    return num - 1 if num else -1


# >>>

# File data Queries <<<
def get_line_from_file(field_type, file_num, query):

    index_file_name = os.path.join(index_dir, f"index_{field_type}{file_num}.txt")
    offsets_file_name = os.path.join(index_dir, f"offset_{field_type}{file_num}.txt")
    offsets = None
    with open(offsets_file_name, "r") as f:
        offsets = f.read().split("\n")

    with open(index_file_name, "r") as f:

        # Binary Search
        lwr, upr = 0, len(offsets) - 2
        while lwr <= upr:
            mid = (lwr + upr) // 2
            f.seek(int(offsets[mid]))
            current_line = f.readline().strip().split()

            if current_line[0] == query:
                return current_line
            elif current_line[0] < query:
                lwr = mid + 1
            else:
                upr = mid - 1
        return []


# >>>

# IDF Queries <<<
IDF_PRE_INDEX = []
IDF_CACHE = {}


def get_token_idf(token):
    global IDF_CACHE

    if token in IDF_CACHE:
        return IDF_CACHE[token]

    file_num = bisect.bisect_left(IDF_PRE_INDEX, token) - 1
    file_name = os.path.join(index_dir, f"idf_{file_num}.txt")
    idf_file_data = None
    with open(file_name, "r") as f:
        idf_file_data = f.read().split("\n")
        tokens = [l.split()[0] for l in idf_file_data]

    token_line_num = bisect.bisect_left(tokens, token)
    if token_line_num == len(tokens) or tokens[token_line_num] != token:
        IDF_CACHE[token] = 0
        return 0
    token_idf = float(idf_file_data[token_line_num].split()[1])
    IDF_CACHE[token] = token_idf
    return token_idf


# >>>

# Title Queries <<<
TITLES_PRE_INDEX = []


def get_title_file_num(enc_doc_id):
    enc_doc_id = normalize_enc_doc_id(enc_doc_id)
    file_num = bisect.bisect_left(TITLES_PRE_INDEX, enc_doc_id)
    return file_num - 1 if file_num else -1


def get_line_from_title_file(enc_doc_id, file_num):
    file_name = os.path.join(index_dir, f"title{file_num}.txt")
    enc_doc_id = normalize_enc_doc_id(enc_doc_id)
    with open(file_name, "r") as f:
        data = f.read().split("\n")
        doc_id = base_64_decode(enc_doc_id)
        first_id_in_file = base_64_decode(data[0].split(maxsplit=1)[0])
        line_num = doc_id - first_id_in_file
        return data[line_num]


# >>>


def calculate_query_score(token, field_type, scores_map, is_field_query=False):

    file_num = get_file_num_for_query(field_type, token)
    index_file_line = get_line_from_file(field_type, file_num, token)
    token_idf = get_token_idf(token)
    field_weight = (
        FIELD_TYPE_TO_WEIGHT_MAP_FIELD_QUERY[field_type]
        if is_field_query
        else FIELD_TYPE_TO_WEIGHT_MAP_NORMAL_QUERY[field_type]
    )
    for document in index_file_line[1:]:
        enc_doc_id, enc_tf = document.split(":")
        if field_type == FIELD_TYPE_TITLE or field_type == FIELD_TYPE_INFOBOX:
            token_tf = 1
        else:
            token_tf = base_64_decode(enc_tf)
        scores_map[enc_doc_id] += field_weight * token_tf * token_idf


def get_search_results(search_string: str):

    search_string = search_string.lower()
    scores_map = defaultdict(int)
    results = []

    if not re.match(r"[t|b|i|c|r|l]:", search_string):
        # Generic query
        all_fields = [
            FIELD_TYPE_TITLE,
            FIELD_TYPE_BODY,
            FIELD_TYPE_INFOBOX,
            FIELD_TYPE_CATEGORIES,
            FIELD_TYPE_EXTERNAL_LINKS,
            FIELD_TYPE_REFERENCES,
        ]

        query_string = search_string
        query = process_query(query_string)

        for field_type in all_fields:
            for token in query:
                calculate_query_score(token, field_type, scores_map, False)
    else:
        # Field specific query
        for match in re.findall(r"([t|b|c|i|l|r]):([^:]*)(?!\S)", search_string):
            field, query_string = match
            query = process_query(query_string)
            for token in query:
                calculate_query_score(token, field, scores_map, True)

    priority_queue = [(-v, k) for k, v in scores_map.items()]
    heapq.heapify(priority_queue)

    while len(results) < NUM_RESULTS_PER_QUERY:
        if len(priority_queue) == 0:
            break
        top_element = heapq.heappop(priority_queue)
        score, enc_doc_id = top_element
        score = -score
        title_file_num = get_title_file_num(enc_doc_id)
        line_from_title_file = get_line_from_title_file(enc_doc_id, title_file_num)
        doc_title = line_from_title_file.split(maxsplit=1)[1]
        if any(doc_title.startswith(meta) for meta in ["Help:", "Module:"]):
            continue
        results.append(f"{enc_doc_id}, {doc_title}")

    return results


if __name__ == "__main__":

    if len(sys.argv) < 4:
        print("Expected two arguments : queries_file, index_dir & output_file")
        exit(1)

    queries_file = sys.argv[1]
    index_dir = sys.argv[2]
    output_file = sys.argv[3]
    # output_file = "queries_op.txt"

    if not os.path.exists(queries_file):
        print("Queries file doesn't exist")
        exit(1)

    if not os.path.exists(index_dir):
        print("Index directory does not exist")
        exit(1)

    if os.path.exists(output_file):
        os.remove(output_file)

    # Preprocessing <<<

    for field_type in [
        FIELD_TYPE_TITLE,
        FIELD_TYPE_BODY,
        FIELD_TYPE_INFOBOX,
        FIELD_TYPE_CATEGORIES,
        FIELD_TYPE_EXTERNAL_LINKS,
        FIELD_TYPE_REFERENCES,
    ]:
        get_document_headings(field_type)

    idf_pre_index_file_name = os.path.join(index_dir, f"idf_preindex.txt")
    with open(idf_pre_index_file_name, "r") as f:
        IDF_PRE_INDEX = f.read().split("\n")

    titles_pre_index_file_name = os.path.join(index_dir, "title_pre_index.txt")
    with open(titles_pre_index_file_name, "r") as f:
        TITLES_PRE_INDEX = [normalize_enc_doc_id(i) for i in f.read().split("\n")]

    # >>>

    with open(output_file, "w") as of:
        with open(queries_file, "r") as qf:
            for query in qf.readlines():

                query = query.strip()
                if len(query) == 0:
                    continue

                # Gather results for current query
                start_time = time.perf_counter()
                results = get_search_results(query)
                elapsed_time = time.perf_counter() - start_time

                # Write results in output file
                if results is not None and len(results) > 0:
                    of.write("\n".join(results))

                of.write(f"\n{elapsed_time}\n\n")
