import heapq
import os
import re
import shutil
import string
import sys
import pickle as pkl

from functools import cache
from collections import defaultdict

import xml.sax
import xml.sax.handler

from Stemmer import Stemmer

UNSTEMMED_TOKENS = set()
STEMMED_TOKENS = set()
ENGLISH_STEMMER = Stemmer("english")

# Constants <<<
FIELD_TYPE_TITLE = "t"
FIELD_TYPE_BODY = "b"
FIELD_TYPE_INFOBOX = "i"
FIELD_TYPE_CATEGORIES = "c"
FIELD_TYPE_EXTERNAL_LINKS = "l"
FIELD_TYPE_REFERENCES = "r"

REGEX_INFOBOX = re.compile(r"{{infobox.*?^}}$", flags=re.M | re.DOTALL)
REGEX_BRACES = re.compile(r"{{.*?}}", flags=re.M)
REGEX_CATEGORY = re.compile(r"\[\[category:(?P<cat>.*?)\]\]")

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

# Configuration variables <<<
NUMBER_OF_PAGES_PER_PREINDEX_FILE = 15_000
NUMBER_OF_TOKENS_PER_FILE = 50_000
NUMBER_OF_TITLES_PER_FILE = 50_000
# >>>

# Base Conversion <<<
ENCODING_CHARS = "".join(
    ["#+", string.digits, string.ascii_uppercase, string.ascii_lowercase]
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
@cache
def stem_word(token):
    return ENGLISH_STEMMER.stemWord(token)


# >>>

# Writing Index Files <<<
def write_article_id_to_title_mappings(titles, offsets, file_count):

    global ARTICLE_TITLE_PRE_INDEX

    file_name = os.path.join(index_dir, f"article_titles_{file_count}.txt")
    with open(file_name, "w") as f:
        f.write("\n".join(titles))

    ARTICLE_TITLE_PRE_INDEX.append(titles[0].split(maxsplit=1)[0])

    # starting_article = titles[0].split()
    # with open(os.path.join(index_dir, "article_titles_pre_index.txt"), "a+") as f:
    #     f.write(starting_article[0])
    #
    # file_name = os.path.join(index_dir, f"article_titles_offset_{file_count}.txt")
    # with open(file_name, "w") as f:
    #     f.write("\n".join(offsets))


def write_temp_idf_files(token_to_idf_map, file_count):

    file_name = os.path.join(index_dir, f"temp_idf_{file_count}.txt")
    with open(file_name, "w") as f:
        lines = [
            f"{token} {token_to_idf_map[token]}"
            for token in sorted(token_to_idf_map.keys())
        ]
        f.write("\n".join(lines))


def write_pages_in_temp_index_files(field_type, index_map, file_count):

    index_filename = os.path.join(
        index_dir, f"temp_index_{field_type}_{file_count}.txt"
    )
    with open(index_filename, "w") as f:
        lines = [
            f"{token} {' '.join(index_map[token])}"
            for token in sorted(index_map.keys())
        ]
        f.writelines("\n".join(lines))


def write_final_index_file(page_count, field_type, data, offsets):

    file_name = os.path.join(index_dir, f"index_{field_type}_{page_count}.txt")

    with open(file_name, "a") as f:
        f.write("\n".join(data))

    file_name = os.path.join(index_dir, f"offsets_{field_type}_{page_count}.pkl")
    with open(file_name, "wb") as f:
        pkl.dump(offsets, f)


def merge_temp_index_files(field_type):

    (
        priority_queue,
        fds,
        top_lines,
        top_line_words,
        page_count,
        top_element,
        buffer_token_count,
        current_frequency,
        current_word,
        current_data,
        data,
        vocab_data,
        offsets,
    ) = ([], {}, {}, {}, 0, (), 1, 0, "", "", [], [], [0])

    for file_num in range(TEMP_INDEX_FILE_COUNT):
        file_name = os.path.join(index_dir, f"temp_index_{field_type}_{file_num}.txt")
        fds[file_num] = open(file_name, "r")
        top_lines[file_num] = fds[file_num].readline().strip()
        if top_lines != "":
            top_line_words[file_num] = top_lines[file_num].split()
            heapq.heappush(priority_queue, (top_line_words[file_num][0], file_num))

    while len(priority_queue) != 0:
        top_element = heapq.heappop(priority_queue)
        new_file_num = top_element[1]

        if buffer_token_count % NUMBER_OF_TOKENS_PER_FILE == 0:
            write_final_index_file(page_count, field_type, data, offsets)
            if data:
                page_count += 1
            data = []
            buffer_token_count = 1
            offsets = [0]

        if current_word == top_element[0] or current_word == "":
            current_frequency += 1
            current_word, _ = top_element
            current_data += " " + " ".join(top_line_words[new_file_num][1:])
        else:
            data.append(current_data)
            offsets.append(len(current_data) + 1 + offsets[-1])
            buffer_token_count += 1
            current_word, _ = top_element
            current_data = top_lines[new_file_num]

            vocab_data.append(f"{current_word} {current_frequency}-{page_count}")
            current_frequency = 0

        top_lines[new_file_num] = fds[new_file_num].readline().strip()
        if top_lines[new_file_num] != "":
            top_line_words[new_file_num] = top_lines[new_file_num].split()
            heapq.heappush(
                priority_queue, (top_line_words[new_file_num][0], new_file_num)
            )
        else:
            fds[new_file_num].close()
            top_line_words[new_file_num] = []
            file_name = os.path.join(
                index_dir, f"temp_index_{field_type}_{new_file_num}.txt"
            )
            os.remove(file_name)

    data.append(current_data)
    offsets.append(len(current_data) + 1 + offsets[-1])
    buffer_token_count += 1
    write_final_index_file(page_count, field_type, data, offsets)

    vocab_data.append(f"{current_word} {current_frequency}-{page_count}")
    file_name = os.path.join(index_dir, f"vocab_{field_type}.txt")
    with open(file_name, "a") as f:
        f.write("\n".join(vocab_data))


def merge_vocab_files():

    priority_queue, top_line_words, fds, top_lines, data = (
        [],
        {},
        {},
        {},
        [],
    )

    fields = [
        FIELD_TYPE_TITLE,
        FIELD_TYPE_BODY,
        FIELD_TYPE_INFOBOX,
        FIELD_TYPE_CATEGORIES,
        FIELD_TYPE_EXTERNAL_LINKS,
        FIELD_TYPE_REFERENCES,
    ]

    for file_num in range(len(fields)):
        file_name = os.path.join(index_dir, f"vocab_{fields[file_num]}.txt")
        fds[file_num] = open(file_name, "r")
        top_lines[file_num] = fds[file_num].readline().strip()
        if top_lines[file_num] != "":
            top_line_words[file_num] = top_lines[file_num].split()
            heapq.heappush(priority_queue, (top_line_words[file_num][0], file_num))

    top_element, current_word, current_data, current_frequency = (), "", "", 0

    while len(priority_queue) > 0:
        top_element = heapq.heappop(priority_queue)
        new_file_num = top_element[1]

        if current_word == top_element[0] or current_word == "":
            current_data = f"{current_data} {fields[new_file_num]}-{top_line_words[new_file_num][1]}"
            current_word = top_element[0]
            current_frequency += 1
        else:
            data.append(current_data)
            current_word = top_element[0]
            current_data = f"{current_word} {fields[new_file_num]}-{top_line_words[new_file_num][1]}"
            current_frequency = 0

        top_lines[new_file_num] = fds[new_file_num].readline().strip()
        if top_lines[new_file_num] == "":
            fds[new_file_num].close()
            top_line_words[new_file_num] = []
            file_name = os.path.join(index_dir, f"vocab_{fields[new_file_num]}.txt")
            os.remove(file_name)
        else:
            top_line_words[new_file_num] = top_lines[new_file_num].split()
            heapq.heappush(
                priority_queue, (top_line_words[new_file_num][0], new_file_num)
            )

    data.append(current_data)

    with open(os.path.join(index_dir, "vocab.txt"), "a") as f:
        f.write("\n".join(data))


def merge_idf_files():

    priority_queue, top_line_words, fds, top_lines, file_number, data = (
        [],
        {},
        {},
        {},
        0,
        [],
    )

    for temp_file_num in range(TEMP_INDEX_FILE_COUNT):
        file_name = os.path.join(index_dir, f"temp_idf_{temp_file_num}.txt")
        fds[temp_file_num] = open(file_name, "r")
        top_lines[temp_file_num] = fds[temp_file_num].readline().strip()
        if top_lines[temp_file_num] != "":
            heapq.heappush(
                priority_queue, (top_lines[temp_file_num].split()[0], temp_file_num)
            )

    top_element, current_word, current_frequency, count, net_count = ("", "", 0, 1, 0)

    while priority_queue:
        top_element = heapq.heappop(priority_queue)
        new_index = top_element[1]

        if count % NUMBER_OF_TOKENS_PER_FILE == 0:
            pass


# >>>

# Indexing <<<
INDEX_MAP_TITLE = defaultdict(list)
INDEX_MAP_BODY = defaultdict(list)
INDEX_MAP_INFOBOX = defaultdict(list)
INDEX_MAP_CATEGORIES = defaultdict(list)
INDEX_MAP_EXTERNAL_LINKS = defaultdict(list)
INDEX_MAP_REFERENCES = defaultdict(list)

ARTICLE_ID_TO_TITLE_MAP = []
ARTICLE_TITLE_PRE_INDEX = []
TOTAL_ARTICLE_COUNT = 0
ARTICLE_TITLES_FILE_OFFSET = [0]
WORD_TO_ARTICLE_COUNT = defaultdict(int)

PAGE_COUNT = 0
ARTICLE_MAPPING_FILE_COUNT = 0
TEMP_INDEX_FILE_COUNT = 0


def create_pre_index(
    title, body, infobox, categories, external_links, references, original_title
):

    global INDEX_MAP_TITLE
    global INDEX_MAP_BODY
    global INDEX_MAP_INFOBOX
    global INDEX_MAP_CATEGORIES
    global INDEX_MAP_EXTERNAL_LINKS
    global INDEX_MAP_REFERENCES
    global PAGE_COUNT
    global TEMP_INDEX_FILE_COUNT

    global ARTICLE_ID_TO_TITLE_MAP
    global ARTICLE_MAPPING_FILE_COUNT
    global TOTAL_ARTICLE_COUNT
    global ARTICLE_TITLES_FILE_OFFSET
    global WORD_TO_ARTICLE_COUNT

    article_id = base_64_encode(PAGE_COUNT)
    # title_file_line = (
    #     f"{article_id} {len(title)} {len(body)} {len(infobox)} {len(categories)}"
    #     f" {len(references)} {len(external_links)} {original_title}"
    # )
    title_file_line = f"{article_id} {original_title}"
    ARTICLE_ID_TO_TITLE_MAP.append(title_file_line)
    # ARTICLE_TITLES_FILE_OFFSET.append(
    #     ARTICLE_TITLES_FILE_OFFSET[-1] + len(title_file_line) + 1
    # )
    TOTAL_ARTICLE_COUNT += 1

    # title_counter = Counter(title)
    # body_counter = Counter(body)
    # infobox_counter = Counter(infobox)
    # categories_counter = Counter(categories)
    # external_links_counter = Counter(external_links)
    # references_counter = Counter(references)
    # combined_counter = (
    #     title_counter
    #     + body_counter
    #     + infobox_counter
    #     + categories_counter
    #     + external_links_counter
    #     + references_counter
    # )

    title_counter = defaultdict(int)
    body_counter = defaultdict(int)
    infobox_counter = defaultdict(int)
    categories_counter = defaultdict(int)
    external_links_counter = defaultdict(int)
    references_counter = defaultdict(int)
    combined_counter = defaultdict(int)

    for token in title:
        title_counter[token] += 1
        combined_counter[token] += 1

    for token in body:
        body_counter[token] += 1
        combined_counter[token] += 1

    for token in infobox:
        infobox_counter[token] += 1
        combined_counter[token] += 1

    for token in categories:
        categories_counter[token] += 1
        combined_counter[token] += 1

    for token in external_links:
        external_links_counter[token] += 1
        combined_counter[token] += 1

    for token in references:
        references_counter[token] += 1
        combined_counter[token] += 1

    for token in combined_counter:
        in_title = title_counter[token]
        in_body = body_counter[token]
        in_infobox = infobox_counter[token]
        in_categories = categories_counter[token]
        in_external_links = external_links_counter[token]
        in_references = references_counter[token]

        if in_title > 0:
            INDEX_MAP_TITLE[token].append(f"{article_id}:{in_title}")
        if in_body > 0:
            INDEX_MAP_BODY[token].append(f"{article_id}:{in_body}")
        if in_infobox > 0:
            INDEX_MAP_INFOBOX[token].append(f"{article_id}:{in_infobox}")
        if in_categories > 0:
            INDEX_MAP_CATEGORIES[token].append(f"{article_id}:{in_categories}")
        if in_external_links > 0:
            INDEX_MAP_EXTERNAL_LINKS[token].append(f"{article_id}:{in_external_links}")
        if in_references > 0:
            INDEX_MAP_REFERENCES[token].append(f"{article_id}:{in_references}")

        WORD_TO_ARTICLE_COUNT[token] += 1

    PAGE_COUNT += 1

    if PAGE_COUNT % NUMBER_OF_TITLES_PER_FILE == 0:
        write_article_id_to_title_mappings(
            ARTICLE_ID_TO_TITLE_MAP,
            ARTICLE_TITLES_FILE_OFFSET,
            ARTICLE_MAPPING_FILE_COUNT,
        )
        ARTICLE_MAPPING_FILE_COUNT += 1
        ARTICLE_TITLES_FILE_OFFSET = [0]
        ARTICLE_ID_TO_TITLE_MAP = []

    if PAGE_COUNT % NUMBER_OF_PAGES_PER_PREINDEX_FILE == 0:

        write_pages_in_temp_index_files(
            FIELD_TYPE_TITLE,
            INDEX_MAP_TITLE,
            TEMP_INDEX_FILE_COUNT,
        )
        write_pages_in_temp_index_files(
            FIELD_TYPE_BODY,
            INDEX_MAP_BODY,
            TEMP_INDEX_FILE_COUNT,
        )
        write_pages_in_temp_index_files(
            FIELD_TYPE_INFOBOX,
            INDEX_MAP_INFOBOX,
            TEMP_INDEX_FILE_COUNT,
        )
        write_pages_in_temp_index_files(
            FIELD_TYPE_CATEGORIES,
            INDEX_MAP_CATEGORIES,
            TEMP_INDEX_FILE_COUNT,
        )
        write_pages_in_temp_index_files(
            FIELD_TYPE_EXTERNAL_LINKS,
            INDEX_MAP_EXTERNAL_LINKS,
            TEMP_INDEX_FILE_COUNT,
        )
        write_pages_in_temp_index_files(
            FIELD_TYPE_REFERENCES,
            INDEX_MAP_REFERENCES,
            TEMP_INDEX_FILE_COUNT,
        )

        INDEX_MAP_TITLE.clear()
        INDEX_MAP_BODY.clear()
        INDEX_MAP_INFOBOX.clear()
        INDEX_MAP_CATEGORIES.clear()
        INDEX_MAP_EXTERNAL_LINKS.clear()
        INDEX_MAP_REFERENCES.clear()

        TEMP_INDEX_FILE_COUNT += 1


# >>>

# Article Parsing <<<
def process_text(title: str, text: str):

    # Fold Case
    text = text.lower()
    title = title.lower()

    # extract references
    for sep in {"== ", " =="}:
        text = text.replace(sep, "==")
    data = text.split("==references==")

    final_title = tokenize_and_stem(title)
    final_body = extract_body(data[0])
    final_infobox = extract_infobox(data[0])
    final_categories = extract_categories(text)

    if len(data) == 1:
        # No references
        final_references = []
        final_external_links = []
    else:
        final_references = extract_references(data[1])
        final_external_links = extract_external_links(data[1])

    return (
        final_title,
        final_body,
        final_infobox,
        final_categories,
        final_external_links,
        final_references,
    )


def tokenize_and_stem(text):

    global UNSTEMMED_TOKENS
    global STEMMED_TOKENS

    text = text.encode("ascii", errors="ignore").decode()

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
        text = text.replace(sym, " ")

    text = text.split()

    for token in text:
        UNSTEMMED_TOKENS.add(token)

    text = [stem_word(token) for token in text]
    text = [
        token
        for token in text
        if (
            (token.isalpha())
            and (token not in ENGLISH_STOPWORDS)
            and (3 < len(token) < 15)
        )
    ]

    for token in text:
        STEMMED_TOKENS.add(token)

    return text


def extract_body(text):

    # remove infobox
    text = REGEX_INFOBOX.sub(repl=" ", string=text)
    # remove any remaining {{}}
    text = REGEX_BRACES.sub(repl=" ", string=text)

    return tokenize_and_stem(text)


def extract_infobox(text):

    start_index = 0
    if not text.startswith("{{infobox"):
        start_index = 1

    infobox = []

    text = text.split("{{infobox")
    for t in text[start_index:]:
        lines = t.split("\n")
        for line in lines:
            if line == "}}":
                break
            infobox.append(line)

    return tokenize_and_stem(" ".join(infobox))


def extract_categories(text):

    matches = REGEX_CATEGORY.findall(string=text)

    return tokenize_and_stem(" ".join(matches))


def extract_references(text):

    text = text.split("\n\n", maxsplit=1)[0].replace("reflist", " ")

    return tokenize_and_stem(text)


def extract_external_links(text):

    text = text.split("==external links==")
    if len(text) == 1:
        return []
    else:
        return tokenize_and_stem(text[1].split("\n\n", maxsplit=1)[0])


# >>>

# XML Parsing <<<
class WikiXMLHandler(xml.sax.ContentHandler):
    """
    This class is the ContentHandler that will be used
    by SAX parser to extract different usefule data from
    XML dump
    """

    def __init__(self):

        self.current_element = ""

        self.article_title = ""
        self.article_text = ""

    def startElement(self, name, attrs):

        self.current_element = name

    def endElement(self, name):

        if name == "page":

            self.article_title = self.article_title.strip()
            self.article_text = self.article_text.strip()

            if not any(
                self.article_title.startswith(meta_title)
                for meta_title in ["Wikipedia:", "File:", "Template:"]
            ):
                (
                    title,
                    body,
                    infobox,
                    categories,
                    external_links,
                    references,
                ) = process_text(self.article_title, self.article_text)

                create_pre_index(
                    title,
                    body,
                    infobox,
                    categories,
                    external_links,
                    references,
                    self.article_title.strip(),
                )

            self.article_title = ""
            self.article_text = ""

    def characters(self, content):

        if self.current_element == "title":
            self.article_title = f"{self.article_title}{content}"

        elif self.current_element == "text":
            self.article_text = f"{self.article_text}{content}"


# >>>

# Running Script <<<
if __name__ == "__main__":

    # Handle Arguments

    if len(sys.argv) < 4:
        print("Expected three arguments")
        exit(1)

    dump_file = sys.argv[1]
    index_dir = sys.argv[2]
    stat_file = sys.argv[3]

    if not os.path.exists(dump_file):
        print("Dump file doesn't exist")
        exit(1)

    if os.path.exists(index_dir):
        shutil.rmtree(index_dir)

    os.mkdir(index_dir)

    # import cProfile, pstats
    #
    # with cProfile.Profile() as prof:

    wiki_xml_handler = WikiXMLHandler()

    xml_parser = xml.sax.make_parser()
    xml_parser.setFeature(xml.sax.handler.feature_namespaces, 0)
    xml_parser.setContentHandler(wiki_xml_handler)
    xml_parser.parse(dump_file)

    if len(ARTICLE_ID_TO_TITLE_MAP) != 0:
        write_article_id_to_title_mappings(
            ARTICLE_ID_TO_TITLE_MAP,
            ARTICLE_TITLES_FILE_OFFSET,
            ARTICLE_MAPPING_FILE_COUNT,
        )
    ARTICLE_ID_TO_TITLE_MAP = []
    ARTICLE_TITLES_FILE_OFFSET = [0]
    ARTICLE_MAPPING_FILE_COUNT += 1

    write_pages_in_temp_index_files(
        FIELD_TYPE_TITLE,
        INDEX_MAP_TITLE,
        TEMP_INDEX_FILE_COUNT,
    )
    write_pages_in_temp_index_files(
        FIELD_TYPE_BODY,
        INDEX_MAP_BODY,
        TEMP_INDEX_FILE_COUNT,
    )
    write_pages_in_temp_index_files(
        FIELD_TYPE_INFOBOX,
        INDEX_MAP_INFOBOX,
        TEMP_INDEX_FILE_COUNT,
    )
    write_pages_in_temp_index_files(
        FIELD_TYPE_CATEGORIES,
        INDEX_MAP_CATEGORIES,
        TEMP_INDEX_FILE_COUNT,
    )
    write_pages_in_temp_index_files(
        FIELD_TYPE_EXTERNAL_LINKS,
        INDEX_MAP_EXTERNAL_LINKS,
        TEMP_INDEX_FILE_COUNT,
    )
    write_pages_in_temp_index_files(
        FIELD_TYPE_REFERENCES,
        INDEX_MAP_REFERENCES,
        TEMP_INDEX_FILE_COUNT,
    )

    INDEX_MAP_TITLE.clear()
    INDEX_MAP_BODY.clear()
    INDEX_MAP_INFOBOX.clear()
    INDEX_MAP_CATEGORIES.clear()
    INDEX_MAP_EXTERNAL_LINKS.clear()
    INDEX_MAP_REFERENCES.clear()

    TEMP_INDEX_FILE_COUNT += 1

    merge_temp_index_files(FIELD_TYPE_TITLE)
    merge_temp_index_files(FIELD_TYPE_BODY)
    merge_temp_index_files(FIELD_TYPE_INFOBOX)
    merge_temp_index_files(FIELD_TYPE_CATEGORIES)
    merge_temp_index_files(FIELD_TYPE_EXTERNAL_LINKS)
    merge_temp_index_files(FIELD_TYPE_REFERENCES)

    merge_vocab_files()

    with open(stat_file, "w") as f:
        f.write(
            f"Total number of tokens encountered in dump : {len(UNSTEMMED_TOKENS):,}\n"
        )
        f.write(f"Total number of tokens in inverted index : {len(STEMMED_TOKENS)}\n")

    # stats = pstats.Stats(prof)
    # stats.sort_stats(pstats.SortKey.TIME)
    # stats.dump_stats(filename="prof.prof")
# >>>
