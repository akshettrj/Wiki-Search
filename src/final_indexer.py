import os
import re
import shutil
import string
import sys

from collections import defaultdict, Counter

import xml.sax
import xml.sax.handler

from nltk.corpus import stopwords
from Stemmer import Stemmer

UNSTEMMED_TOKENS = set()
ENGLISH_STOPWORDS = set(stopwords.words("english"))
ENGLISH_STEMMER = Stemmer("english")

# Constants <<<
FIELD_TYPE_TITLE = "t"
FIELD_TYPE_BODY = "b"
FIELD_TYPE_INFOBOX = "i"
FIELD_TYPE_CATEGORIES = "c"
FIELD_TYPE_EXTERNAL_LINKS = "l"
FIELD_TYPE_REFERENCES = "r"
# >>>

# Configuration variables <<<
NUMBER_OF_PAGES_PER_PREINDEX_FILE = 15_000
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
    return "".join(reversed(chars))


def base_64_decode(chars):
    num = 0
    for char in chars:
        num = num * ENCODING_BASE + ENCODING_CHAR_TO_INDEX[char]
    return num


# >>>

# Writing Index Files <<<
def write_pages_in_temp_index_files(field_type, index_map, file_count):
    index_filename = os.path.join(index_dir, f"index_{field_type}_{file_count}.txt")
    with open(index_filename, "w") as f:
        lines = []
        for token in sorted(index_map.keys()):
            line = " ".join([token, " ".join(index_map[token])])
            lines.append(line + "\n")
        f.writelines(lines)


# >>>

# Indexing <<<
INDEX_MAP_TITLE = defaultdict(list)
INDEX_MAP_BODY = defaultdict(list)
INDEX_MAP_INFOBOX = defaultdict(list)
INDEX_MAP_CATEGORIES = defaultdict(list)
INDEX_MAP_EXTERNAL_LINKS = defaultdict(list)
INDEX_MAP_REFERENCES = defaultdict(list)
PAGE_COUNT = 0
TEMP_INDEX_FILE_COUNT = 0


def create_pre_index(title, body, infobox, categories, external_links, references):

    global INDEX_MAP_TITLE
    global INDEX_MAP_BODY
    global INDEX_MAP_INFOBOX
    global INDEX_MAP_CATEGORIES
    global INDEX_MAP_EXTERNAL_LINKS
    global INDEX_MAP_REFERENCES
    global PAGE_COUNT
    global TEMP_INDEX_FILE_COUNT

    article_id = base_64_encode(PAGE_COUNT)

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
            INDEX_MAP_TITLE[token].append(article_id)
        if in_body > 0:
            INDEX_MAP_BODY[token].append(article_id)
        if in_infobox > 0:
            INDEX_MAP_INFOBOX[token].append(article_id)
        if in_categories > 0:
            INDEX_MAP_CATEGORIES[token].append(article_id)
        if in_external_links > 0:
            INDEX_MAP_EXTERNAL_LINKS[token].append(article_id)
        if in_references > 0:
            INDEX_MAP_REFERENCES[token].append(article_id)

    PAGE_COUNT += 1
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
    for sep in {"== references ==", "==references ==", "== references=="}:
        text = text.replace(sep, "==references==")
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

    text = text.encode("ascii", errors="ignore").decode()

    for sym in {"&nbsp;", "&lt;", "&gt;", "&amp;", "&quot;", "&apos;"}:
        text = text.replace(sym, " ")

    text = re.sub(r"\W+", r" ", text)

    # for sym in {
    #     "—",
    #     "%",
    #     "$",
    #     "'",
    #     "~",
    #     "|",
    #     ".",
    #     "*",
    #     "[",
    #     "]",
    #     ":",
    #     ";",
    #     ",",
    #     "{",
    #     "}",
    #     "(",
    #     ")",
    #     "=",
    #     "+",
    #     "-",
    #     "_",
    #     "#",
    #     "!",
    #     "`",
    #     '"',
    #     "?",
    #     "/",
    #     ">",
    #     "<",
    #     "&",
    #     "\\",
    # }:
    #     text = text.replace(sym, " ")

    text = text.split()

    text = [token for token in text if token not in ENGLISH_STOPWORDS]
    for token in text:
        UNSTEMMED_TOKENS.add(token)

    text = list(ENGLISH_STEMMER.stemWords(text))

    return text


def extract_body(text):

    # remove infobox
    text = re.sub(
        pattern=r"{{infobox.*?^}}$",
        repl=r" ",
        string=text,
        flags=re.DOTALL | re.M,
    )
    # remove any remaining {{}}
    text = re.sub(
        pattern=r"{{.*?}}",
        repl=r" ",
        string=text,
        flags=re.M,
    )

    return tokenize_and_stem(text)


def extract_infobox(text):

    matches = re.findall(
        pattern="{{infobox(?P<body>.*?)^}}$",
        string=text,
        flags=re.DOTALL | re.M,
    )

    return tokenize_and_stem(" ".join(matches))


def extract_categories(text):

    matches = re.findall(
        pattern=r"\[\[category:(?P<cat>.*?)\]\]",
        string=text,
    )

    return tokenize_and_stem(" ".join(matches))


def extract_references(text):

    text = text.split("\n\n")[0].replace("reflist", " ")

    return tokenize_and_stem(text)


def extract_external_links(text):

    for sep in {
        "== external links ==",
        "==external links ==",
        "== external links==",
    }:
        text = text.replace(sep, "==external links==")
    text = text.split("==external links==")
    if len(text) == 1:
        return []
    else:
        return tokenize_and_stem(text[1].split("\n\n")[0])


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

        self.article_id = ""
        self.article_title = ""
        self.article_text = ""

    def startElement(self, name, attrs):

        self.current_element = name

    def endElement(self, name):

        if name == "page":

            if not self.article_title.startswith("Wikipedia:"):
                (
                    title,
                    body,
                    infobox,
                    categories,
                    external_links,
                    references,
                ) = process_text(self.article_title, self.article_text)

                create_pre_index(
                    title, body, infobox, categories, external_links, references
                )

            self.article_id = ""
            self.article_title = ""
            self.article_text = ""

    def characters(self, content):

        if self.current_element == "id" and self.article_id == "":
            self.article_id = content

        elif self.current_element == "title":
            self.article_title += content

        elif self.current_element == "text":
            self.article_text += content


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

    import cProfile
    import pstats

    with cProfile.Profile() as pr:

        # Start Parsing

        wiki_xml_handler = WikiXMLHandler()

        xml_parser = xml.sax.make_parser()
        xml_parser.setFeature(xml.sax.handler.feature_namespaces, 0)
        xml_parser.setContentHandler(wiki_xml_handler)
        xml_parser.parse(dump_file)

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

    stats = pstats.Stats(pr)
    stats.sort_stats(pstats.SortKey.TIME)
    # stats.print_stats()
    stats.dump_stats(filename="needs_profiling.prof")
