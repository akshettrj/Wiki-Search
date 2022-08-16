import heapq
import os
import re
import shutil
import string
import sys

from collections import defaultdict, Counter
from typing import OrderedDict

import xml.sax
import xml.sax.handler

from nltk.corpus import stopwords
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

ENGLISH_STOPWORDS = set(stopwords.words("english"))
# >>>

# Configuration variables <<<
NUMBER_OF_PAGES_PER_PREINDEX_FILE = 15_000
NUMBER_OF_TOKENS_PER_FILE = 50_000
NUMBER_OF_TITLES_PER_FILE = 50_000
# >>>

# Base Conversion <<<
ENCODING_CHARS = string.digits + string.ascii_lowercase + string.ascii_uppercase + "+="
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

# Writing Index Files <<<
def write_article_id_to_title_mappings(index_map, file_count):

    file_name = os.path.join(index_dir, f"article_titles_{file_count}.txt")
    with open(file_name, "w") as f:
        lines = [
            f"{index_map[num][0]}:{index_map[num][1]}" for num in sorted(index_map)
        ]
        f.write("\n".join(lines))


def write_pages_in_temp_index_files(field_type, index_map, file_count):

    index_filename = os.path.join(
        index_dir, f"temp_index_{field_type}_{file_count}.txt"
    )
    with open(index_filename, "w") as f:
        lines = []
        for token in sorted(index_map.keys()):
            line = f"{token} {' '.join(index_map[token])}"
            lines.append(line + "\n")
        f.writelines(lines)


def write_final_index_file(page_count, field_type, data):

    file_name = os.path.join(index_dir, f"index_{field_type}_{page_count}.txt")

    if not data:
        return

    with open(file_name, "a") as f:
        f.write("\n".join(data))


def merge_temp_index_files(field_type):

    priority_queue = []
    fds = {}
    top_lines = {}
    top_line_words = {}
    page_count = 0

    top_element = ()
    count = 1
    current_word = ""
    current_data = ""
    data = []

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

        if count % NUMBER_OF_TOKENS_PER_FILE == 0:
            write_final_index_file(page_count, field_type, data)
            if data:
                page_count += 1
            data = []
            count = 1

        if current_word == top_element[0] or current_word == "":
            current_word, _ = top_element
            current_data += " "
            current_data += " ".join(top_line_words[new_file_num][1:])
        else:
            data.append(current_data)
            count += 1
            current_word, _ = top_element
            current_data = top_lines[new_file_num]

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
    count += 1
    write_final_index_file(page_count, field_type, data)


# >>>

# Indexing <<<
INDEX_MAP_TITLE = defaultdict(list)
INDEX_MAP_BODY = defaultdict(list)
INDEX_MAP_INFOBOX = defaultdict(list)
INDEX_MAP_CATEGORIES = defaultdict(list)
INDEX_MAP_EXTERNAL_LINKS = defaultdict(list)
INDEX_MAP_REFERENCES = defaultdict(list)

ARTICLE_ID_TO_TITLE_MAP = dict()

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

    article_id = base_64_encode(PAGE_COUNT)
    ARTICLE_ID_TO_TITLE_MAP[PAGE_COUNT] = (article_id, original_title)
    # print(ARTICLE_ID_TO_TITLE_MAP[PAGE_COUNT])

    title_counter = Counter(title)
    body_counter = Counter(body)
    infobox_counter = Counter(infobox)
    categories_counter = Counter(categories)
    external_links_counter = Counter(external_links)
    references_counter = Counter(references)
    combined_counter = (
        title_counter
        + body_counter
        + infobox_counter
        + categories_counter
        + external_links_counter
        + references_counter
    )

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

    PAGE_COUNT += 1

    if PAGE_COUNT % NUMBER_OF_TITLES_PER_FILE == 0:
        write_article_id_to_title_mappings(
            ARTICLE_ID_TO_TITLE_MAP, ARTICLE_MAPPING_FILE_COUNT
        )
        ARTICLE_MAPPING_FILE_COUNT += 1
        ARTICLE_ID_TO_TITLE_MAP.clear()

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

    text = list(ENGLISH_STEMMER.stemWords(text))
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
                self.article_title.startswith(s)
                for s in {"Wikipedia:", "File:", "Template:"}
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

if __name__ == "__main__":

    # Handler Arguments

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

    wiki_xml_handler = WikiXMLHandler()

    xml_parser = xml.sax.make_parser()
    xml_parser.setFeature(xml.sax.handler.feature_namespaces, 0)
    xml_parser.setContentHandler(wiki_xml_handler)
    xml_parser.parse(dump_file)

    if len(ARTICLE_ID_TO_TITLE_MAP) != 0:
        write_article_id_to_title_mappings(
            ARTICLE_ID_TO_TITLE_MAP, ARTICLE_MAPPING_FILE_COUNT
        )
    ARTICLE_ID_TO_TITLE_MAP.clear()

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

    with open(stat_file, "w") as f:
        f.write(
            f"Total number of tokens encountered in dump : {len(UNSTEMMED_TOKENS):,}\n"
        )
        f.write(f"Total number of tokens in inverted index : {len(STEMMED_TOKENS):,}\n")
