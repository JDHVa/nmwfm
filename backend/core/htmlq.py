import re

from lxml import etree, html

_TOKEN = re.compile(
    r"""\s*(?P<comb>>)\s*|(?P<ws>\s+)|(?P<comp>(?:[a-zA-Z][\w-]*|\*)?(?:\#[\w-]+|\.[\w-]+|\[[^\]]+\])*)"""
)
_PART = re.compile(
    r"""(?P<tag>^[a-zA-Z][\w-]*|^\*)|\#(?P<id>[\w-]+)|\.(?P<cls>[\w-]+)|\[(?P<attr>[^\]]+)\]"""
)
_ATTR = re.compile(r"""^\s*([\w:-]+)\s*(?:([*^$]?=)\s*(?:"([^"]*)"|'([^']*)'|(\S+)))?\s*$""")

BLOCK_TAGS = {
    "p",
    "div",
    "ul",
    "ol",
    "table",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
}


def _quote(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    return "concat(" + ', "\'", '.join(f"'{p}'" for p in value.split("'")) + ")"


def _compound_to_xpath(comp: str) -> str:
    tag = "*"
    conds: list[str] = []
    for m in _PART.finditer(comp):
        if m.group("tag"):
            tag = m.group("tag")
        elif m.group("id"):
            conds.append(f"@id={_quote(m.group('id'))}")
        elif m.group("cls"):
            conds.append(
                "contains(concat(' ', normalize-space(@class), ' '), "
                + _quote(" " + m.group("cls") + " ")
                + ")"
            )
        elif m.group("attr"):
            am = _ATTR.match(m.group("attr"))
            if not am:
                raise ValueError(f"Selector de atributo no soportado: {comp}")
            name, op, v1, v2, v3 = am.groups()
            if op is None:
                conds.append(f"@{name}")
                continue
            val = _quote(next(v for v in (v1, v2, v3) if v is not None))
            if op == "=":
                conds.append(f"@{name}={val}")
            elif op == "*=":
                conds.append(f"contains(@{name}, {val})")
            elif op == "^=":
                conds.append(f"starts-with(@{name}, {val})")
            else:
                conds.append(
                    f"substring(@{name}, string-length(@{name}) - string-length({val}) + 1)={val}"
                )
    return tag + "".join(f"[{c}]" for c in conds)


def css_to_xpath(css: str) -> str:
    alternatives = []
    for group in _split_commas(css):
        axis = ".//"
        out = ""
        pending_child = False
        pos = 0
        group = group.strip()
        while pos < len(group):
            m = _TOKEN.match(group, pos)
            if not m or m.end() == pos:
                raise ValueError(f"Selector no soportado: {css}")
            pos = m.end()
            if m.group("comb"):
                pending_child = True
            elif m.group("comp"):
                step = _compound_to_xpath(m.group("comp"))
                out += (axis if not out else ("/" if pending_child else "//")) + step
                pending_child = False
        alternatives.append(out)
    return " | ".join(alternatives)


def _split_commas(css: str) -> list[str]:
    parts, depth, quote, buf = [], 0, None, []
    for ch in css:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return parts


def parse(markup: str) -> html.HtmlElement:
    return html.fromstring(f"<div>{markup}</div>") if markup.strip() else html.fromstring("<div/>")


def select(el, css: str) -> list:
    return el.xpath(css_to_xpath(css))


def select_one(el, css: str):
    found = select(el, css)
    return found[0] if found else None


def text_of(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.text_content().replace("\xa0", " ")).strip()


def has_class(el, name: str) -> bool:
    return name in (el.get("class") or "").split()


_WS = re.compile(r"[ \t\r\n\f\v]+")


def _text_node(text: str | None, pre: bool) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    return text if pre else _WS.sub(" ", text)


def _wrap(marker: str, inner: str) -> str:
    stripped = inner.strip()
    if not stripped:
        return inner
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()) :]
    return f"{lead}{marker}{stripped}{marker}{trail}"


def _inline(el, pre: bool = False) -> str:
    parts = [_text_node(el.text, pre)]
    for child in el:
        if not isinstance(child.tag, str):
            parts.append(_text_node(child.tail, pre))
            continue
        tag = child.tag.lower()
        if tag == "br":
            parts.append("\n")
        elif tag in ("strong", "b"):
            parts.append(_wrap("**", _inline(child, pre)))
        elif tag in ("em", "i"):
            parts.append(_wrap("*", _inline(child, pre)))
        elif tag == "code":
            parts.append(_wrap("`", _inline(child, pre)))
        elif tag in ("script", "style"):
            pass
        else:
            parts.append(_inline(child, pre))
        parts.append(_text_node(child.tail, pre))
    return "".join(parts)


def _clean_inline(text: str) -> str:
    lines = [ln.strip() for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def _has_block_child(el) -> bool:
    return any(isinstance(c.tag, str) and c.tag.lower() in BLOCK_TAGS for c in el.iterchildren())


def _container_blocks(el) -> list[str]:
    blocks: list[str] = []
    buf = [_text_node(el.text, False)]

    def flush():
        text = _clean_inline("".join(buf))
        if text:
            blocks.append(text)
        buf.clear()

    for child in el:
        if isinstance(child.tag, str) and child.tag.lower() in BLOCK_TAGS:
            flush()
            blocks.extend(_block(child))
            buf.append(_text_node(child.tail, False))
        elif isinstance(child.tag, str):
            wrapper = html.fromstring("<div/>")
            wrapper.append(_clone(child))
            buf.append(_inline(wrapper))
            buf.append(_text_node(child.tail, False))
    flush()
    return blocks


def _clone(el):
    clone = html.fromstring(etree.tostring(el, encoding="unicode", with_tail=False))
    return clone


def _list_block(el, ordered: bool, indent: int = 0) -> str:
    lines: list[str] = []
    n = 0
    for li in el.iterchildren():
        if not isinstance(li.tag, str) or li.tag.lower() != "li":
            continue
        n += 1
        marker = f"{n}." if ordered else "-"
        pad = "  " * indent
        head: list[str] = [_text_node(li.text, False)]
        nested: list[str] = []
        for child in li:
            ctag = child.tag.lower() if isinstance(child.tag, str) else ""
            if ctag in ("ul", "ol"):
                nested.append(_list_block(child, ctag == "ol", indent + 1))
            elif ctag in BLOCK_TAGS:
                head.append(" " + _clean_inline(_inline(child)))
            elif ctag:
                wrapper = html.fromstring("<div/>")
                wrapper.append(_clone(child))
                head.append(_inline(wrapper))
            head.append(_text_node(child.tail, False))
        text = " ".join(_clean_inline("".join(head)).split("\n"))
        lines.append(f"{pad}{marker} {text}".rstrip())
        lines.extend(nested)
    return "\n".join(lines)


def _table_block(el) -> str:
    rows = []
    for tr in el.xpath(".//tr"):
        cells = [
            " ".join(_clean_inline(_inline(c)).split("\n")).replace("|", "\\|")
            for c in tr.xpath("./th|./td")
        ]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
    out += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(out)


def _block(el) -> list[str]:
    tag = el.tag.lower()
    if tag in ("ul", "ol"):
        text = _list_block(el, tag == "ol")
        return [text] if text else []
    if tag == "table":
        text = _table_block(el)
        return [text] if text else []
    if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
        text = _clean_inline(_inline(el)).replace("\n", " ")
        return [f"{'#' * int(tag[1])} {text}"] if text else []
    if tag == "blockquote":
        inner = _container_blocks(el)
        return ["\n".join("> " + ln for ln in b.split("\n")) for b in inner]
    if tag in ("div", "p", "pre") and _has_block_child(el):
        return _container_blocks(el)
    text = _clean_inline(_inline(el, pre=False))
    return [text] if text else []


def html_to_markdown(markup_or_el) -> str:
    el = parse(markup_or_el) if isinstance(markup_or_el, str) else markup_or_el
    blocks = _container_blocks(el)
    md = "\n\n".join(blocks)
    return re.sub(r"\n{3,}", "\n\n", md).strip()
