"""文本预处理与消融开关。

数据来自新闻组/邮件语料，原始文本中包含大量与主题无关的结构化噪声：
邮件头（From / Organization / Lines / NNTP-Posting-Host ...）、引用回复
（以 ">" 开头的行）、签名档、邮箱地址与 URL。

实验规范 3/5 要求「只用训练集确定处理规则」。本模块的清洗规则均为**无参
数的确定性规则**（不依赖语料统计量），因此对训练集与验证/测试集使用同一
函数即可，不会引入数据泄露；唯一依赖语料的部件（TF-IDF 词表与 IDF）在
features.py 中严格只在训练集上 fit。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

try:  # 词干化是可选增强，缺少 nltk 时自动退化为不做词干化
    from nltk.stem import SnowballStemmer

    _STEMMER = SnowballStemmer("english")
    NLTK_AVAILABLE = True
except Exception:  # pragma: no cover
    _STEMMER = None
    NLTK_AVAILABLE = False

# 需要剥离的邮件头字段（Subject 例外，它携带主题信息，会被保留）
_HEADER_RE = re.compile(
    r"^(from|organization|lines|reply-to|nntp-posting-host|distribution|"
    r"newsgroups|followup-to|x-newsreader|path|message-id|date|sender)\s*:.*$",
    re.IGNORECASE | re.MULTILINE,
)
_SUBJECT_RE = re.compile(r"^subject\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"(https?://\S+|www\.\S+)")
_QUOTE_LINE_RE = re.compile(r"^\s*>.*$", re.MULTILINE)          # 引用行
_ATTR_LINE_RE = re.compile(r"in article\s*<[^>]*>.*?(writes|wrote)\s*:?", re.IGNORECASE)
_ARTICLE_ID_RE = re.compile(r"<[^<>@\s]+@[^<>\s]+>")             # Message-ID
_SIG_RE = re.compile(r"\n--\s*\n.*$", re.DOTALL)                # 签名档
_NON_ALPHA_RE = re.compile(r"[^a-z\s]")
_WS_RE = re.compile(r"\s+")


@dataclass
class CleanConfig:
    """每一步清洗都是可开关的，便于做消融实验。"""

    strip_headers: bool = True   # 去邮件头（保留 Subject 正文）
    remove_quotes: bool = True   # 去引用回复与追帖行
    remove_signature: bool = True
    mask_entities: bool = True   # 邮箱/URL/Message-ID 替换为占位符
    lowercase: bool = True
    remove_stopwords: bool = True
    min_token_len: int = 2
    stem: bool = False           # 词干化（Porter/Snowball）

    name: str = "custom"

    def describe(self) -> str:
        flags = []
        if self.strip_headers:
            flags.append("去邮件头")
        if self.remove_quotes:
            flags.append("去引用")
        if self.remove_signature:
            flags.append("去签名")
        if self.mask_entities:
            flags.append("屏蔽邮箱/URL")
        if self.remove_stopwords:
            flags.append("去停用词")
        if self.stem:
            flags.append("词干化")
        return " + ".join(flags) if flags else "不清洗"


def _strip_headers(text: str) -> str:
    """剥离邮件头，并把 Subject 的内容并入正文。"""
    head, sep, body = text.partition("\n\n")
    if not sep:  # 没有空行分隔，说明整个文档就是头部或纯正文
        subject = _SUBJECT_RE.search(text)
        if subject:
            rest = _HEADER_RE.sub("", text)
            return f"{subject.group(1)}\n{rest}"
        return text
    subject = _SUBJECT_RE.search(head)
    subject_text = subject.group(1) if subject else ""
    return f"{subject_text}\n{body}"


def clean_text(text: str, cfg: CleanConfig) -> str:
    """按配置清洗单篇文档；同一函数用于训练/验证/测试，规则一致。"""
    if not isinstance(text, str):
        text = "" if text is None else str(text)

    if cfg.strip_headers:
        text = _strip_headers(text)
    if cfg.remove_signature:
        text = _SIG_RE.sub(" ", text)
    if cfg.remove_quotes:
        text = _QUOTE_LINE_RE.sub(" ", text)
        text = _ATTR_LINE_RE.sub(" ", text)
    if cfg.mask_entities:
        text = _EMAIL_RE.sub(" ", text)
        text = _URL_RE.sub(" ", text)
        text = _ARTICLE_ID_RE.sub(" ", text)

    if cfg.lowercase:
        text = text.lower()
    text = _NON_ALPHA_RE.sub(" ", text)   # 去标点/数字，只保留字母
    tokens = _WS_RE.sub(" ", text).strip().split()

    if cfg.remove_stopwords:
        tokens = [t for t in tokens if t not in ENGLISH_STOP_WORDS]
    if cfg.min_token_len > 1:
        tokens = [t for t in tokens if len(t) >= cfg.min_token_len]
    if cfg.stem and _STEMMER is not None:
        tokens = [_STEMMER.stem(t) for t in tokens]

    return " ".join(tokens)


def clean_corpus(texts: list[str], cfg: CleanConfig) -> list[str]:
    return [clean_text(t, cfg) for t in texts]


# ---------------------------------------------------------------------------
# 预置的候选清洗方案（用于消融实验 A）
# ---------------------------------------------------------------------------
def preset_configs() -> dict[str, CleanConfig]:
    """从「不做任何清洗」到「完整清洗」的递进方案。"""
    return {
        "C0_不清洗": CleanConfig(
            strip_headers=False, remove_quotes=False, remove_signature=False,
            mask_entities=False, lowercase=False, remove_stopwords=False,
            min_token_len=1, stem=False, name="C0_不清洗",
        ),
        "C1_基础归一化": CleanConfig(
            strip_headers=False, remove_quotes=False, remove_signature=False,
            mask_entities=False, lowercase=True, remove_stopwords=False,
            min_token_len=1, stem=False, name="C1_基础归一化",
        ),
        "C2_去邮件头": CleanConfig(
            strip_headers=True, remove_quotes=False, remove_signature=False,
            mask_entities=True, lowercase=True, remove_stopwords=False,
            min_token_len=1, stem=False, name="C2_去邮件头",
        ),
        "C3_去邮件头+去引用": CleanConfig(
            strip_headers=True, remove_quotes=True, remove_signature=True,
            mask_entities=True, lowercase=True, remove_stopwords=False,
            min_token_len=1, stem=False, name="C3_去邮件头+去引用",
        ),
        "C4_完整清洗": CleanConfig(
            strip_headers=True, remove_quotes=True, remove_signature=True,
            mask_entities=True, lowercase=True, remove_stopwords=True,
            min_token_len=2, stem=False, name="C4_完整清洗",
        ),
        "C5_完整清洗+词干化": CleanConfig(
            strip_headers=True, remove_quotes=True, remove_signature=True,
            mask_entities=True, lowercase=True, remove_stopwords=True,
            min_token_len=2, stem=True, name="C5_完整清洗+词干化",
        ),
    }
