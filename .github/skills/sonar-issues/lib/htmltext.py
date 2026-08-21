"""Convert SonarQube rule-description HTML into readable markdown-ish text (stdlib only)."""
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.chunks = []
        self.in_pre = False

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.in_pre = True
            self.chunks.append("\n```\n")
        elif tag in ("p", "ul", "ol", "div", "table", "tr"):
            self.chunks.append("\n")
        elif tag == "br":
            self.chunks.append("\n")
        elif tag == "li":
            self.chunks.append("\n- ")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.chunks.append("\n\n**")
        elif tag in ("strong", "b"):
            self.chunks.append("**")
        elif tag == "code" and not self.in_pre:
            self.chunks.append("`")

    def _rstrip_last(self):
        if self.chunks and self.chunks[-1].endswith(" "):
            self.chunks[-1] = self.chunks[-1].rstrip(" ")

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "code"):
            self._rstrip_last()
        if tag == "pre":
            self.in_pre = False
            self.chunks.append("\n```\n")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.chunks.append("**\n")
        elif tag in ("strong", "b"):
            self.chunks.append("**")
        elif tag == "code" and not self.in_pre:
            self.chunks.append("`")
        elif tag in ("p", "ul", "ol"):
            self.chunks.append("\n")

    def handle_data(self, data):
        if self.in_pre:
            self.chunks.append(data)
        else:
            collapsed = " ".join(data.split())
            if collapsed:
                self.chunks.append(collapsed + " ")


def html_to_markdown(html):
    if not html:
        return ""
    parser = _TextExtractor()
    parser.feed(html)
    text = "".join(parser.chunks)
    # collapse >2 consecutive blank lines
    lines = [line.rstrip() for line in text.splitlines()]
    out = []
    blank = 0
    for line in lines:
        if not line:
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        out.append(line)
    return "\n".join(out).strip()
