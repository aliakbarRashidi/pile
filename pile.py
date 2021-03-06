import sys
import re
from pathlib import Path
import json
import os
import os.path
import click

re_date = re.compile("(\d\d\d\d-\d\d-\d\d)(.*)")
re_ext = re.compile(".*?[.]([a-zA-Z]{1,3})")
re_kvtag = re.compile("[#]([A-Za-z0-9]+)=([A-Za-z0-9]+)")
re_tag = re.compile("[#][A-Za-z0-9]+")

def tag2str(tag):
    return '#' + tag

def str2tag(s):
    return s.lstrip("#")

def kvtag2str(k,v):
    return "#" + k + "=" + v

class Document:
    "A managed document"
    
    def __init__(self, date, tags, kvtags, title, ext, path):
        self.date = date
        self.tags = tags
        self.kvtags = kvtags
        self.ext = ext
        self.title = title
        self.path = path

    @staticmethod
    def from_path(path):
        if path.name.startswith("."):
            raise ValueError("Hidden files are not allowed: " + path.name)

        name = path.name

        # Split off extension
        base, ext = os.path.splitext(name)

        # Split off date
        match = re_date.match(base)
        rest = None
        date = None
        if match:
            date = match.group(1)
            rest = match.group(2)
        else:
            raise ValueError("No date field found " + name)

        # Filename seems ok.
        # Causes IO(?) Check last
        if not path.is_file():
            raise ValueError("Path not a file")

        # Extract kv-tags
        kvtags = dict(re_kvtag.findall(rest))
        rest = re_kvtag.sub("", rest)

        # Extract tags
        tags = [ str2tag(tag_str) for tag_str in re_tag.findall(rest) ]
        tags = list(set(tags))
        tags.sort()
        rest = re_tag.sub("", rest)

        # Cleanup title
        rest = re.sub("[_,|:]", " ", rest)
        rest = re.sub("  +", " ", rest)
        rest = rest.strip(" ")
        title = rest
        return Document(date, tags, kvtags, title, ext, path)
        
    def text(self):
        tags = "".join([ tag2str(t) + " " for t in self.tags ])
        kvtags = "".join([ kvtag2str(k,v) + " " for k,v in self.kvtags.items()])
        return '{} {}{}{}{}'.format(self.date, tags, kvtags, self.title, self.ext)

    def normalize(self):
        q = self.path.with_name(self.text())
        self.path.rename(q)
        self.path = q

    def move_to_dir(self, target):
        q = Path(target) / self.path.name
        self.path.rename(q)
        self.path = q

    def name(self):
        return self.path.name

    def has_tag(self, tag):
        return tag in self.tags

    def tag_list(self):
        return self.tags

    def tag_add(self, tag):
        "Add tag to tags list"
        if not tag in self.tags:
            self.tags += [ tag ]
            self.tags.sort()
            self.normalize()
            
    def tag_rm(self, tag):
        "remove tag from internal tag list. Need to normalize() to change file name"
        if tag in self.tags:
            self.tags = [ t for t in self.tags if t != tag ]
            self.normalize()

class Pile():
    "A pile of managed documents"

    def __init__(self, backing_dir):
        self.docs = []
        self.backing_dir = Path(backing_dir)
        assert(self.backing_dir.is_dir())

    def __iter__(self):
        "iterate over documents within the pile"
        return iter(self.docs)

    def add(self, doc):
        "Throw a doc to onto the pile"
        self.docs.append(doc)

    @staticmethod
    def from_folder(path):
        pile = Pile(path)
        for p in Path(path).iterdir():
            try:
                pile.add(Document.from_path(p))
            except ValueError as e:
                pass
        return pile

    @staticmethod
    def leftovers(path):
        "returns all paths that are not valid documents"
        pile = Pile(path)
        for p in Path(path).iterdir():
            try:
                pile.add(Document.from_path(p))
            except ValueError as e:
                yield p

    def extract(self, tag):
        "moves all documents tagged with $tag into a subfolder"
        tagdir = self.backing_dir / tag2str(tag)
        if not tagdir.exists():
            tagdir.mkdir()

        for doc in self:
            if doc.has_tag(tag):
                doc.move_to_dir(tagdir)
                doc.tag_rm(tag)
