#!/usr/bin/env python3
"""
Hybrid Scholar — 并行搜索 + 交叉验证

同时调用 OpenAlex 和 AnySearch 学术搜索，对结果进行去重和交叉验证。
当同一篇论文同时被两个数据源收录时，标记为「交叉验证」，可信度更高。
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from openalex_scholar import OpenAlexScholar, Paper
from anysearch_academic import AnySearchAcademic


def _configure_stdio() -> None:
    """Avoid UnicodeEncodeError on Windows consoles using legacy encodings."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


_configure_stdio()


# ---------------------------------------------------------------------------
# 搜索结果联合数据类
# ---------------------------------------------------------------------------

@dataclass
class HybridPaper:
    """融合论文（带来源追踪）"""
    title: str
    authors: List[str]
    year: Optional[int]
    citations: int
    doi: Optional[str]
    abstract: Optional[str]
    sources: List[str] = field(default_factory=list)
    venue: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    url: Optional[str] = None
    # sources = ["openalex"], ["anysearch"], 或 ["openalex", "anysearch"]

    @property
    def cross_validated(self) -> bool:
        return len(self.sources) >= 2

    @property
    def source_tag(self) -> str:
        if self.cross_validated:
            return "✓ 交叉验证"
        return self.sources[0] if self.sources else "?"

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "citations": self.citations,
            "doi": self.doi,
            "abstract": self.abstract,
            "sources": self.sources,
            "cross_validated": self.cross_validated,
            "venue": self.venue,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "url": self.url,
        }


# ---------------------------------------------------------------------------
# Hybrid Scholar
# ---------------------------------------------------------------------------

class HybridScholar:
    """并行搜索 + 交叉验证器"""

    def __init__(self, email: Optional[str] = None,
                 anysearch_api_key: Optional[str] = None):
        self.openalex = OpenAlexScholar(email=email)
        self.anysearch = AnySearchAcademic(api_key=anysearch_api_key)

    def search_papers(
        self,
        query: str,
        limit: int = 8,
        sort: str = "relevance",
        min_citations: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        field_filter: Optional[str] = None,
        openalex_only: bool = False,
        anysearch_only: bool = False,
    ) -> Dict[str, Any]:
        """
        并行搜索 + 交叉验证。

        Args:
            query: 搜索关键词
            limit: 最终返回结果数量
            sort: 排序方式（仅 OpenAlex）
            min_citations: 最低引用量（仅 OpenAlex）
            year_from / year_to: 年份范围（仅 OpenAlex）
            field_filter: 领域过滤（仅 OpenAlex）
            openalex_only: 仅用 OpenAlex
            anysearch_only: 仅用 AnySearch

        Returns:
            {
                "cross_validated": [...],   # 同时被两个源收录
                "openalex_only": [...],     # 仅 OpenAlex
                "anysearch_only": [...],    # 仅 AnySearch
                "stats": {...},
            }
        """
        self._current_query = query

        # 决定启用哪些源
        use_oa = not anysearch_only
        use_any = not openalex_only

        # 为了去重效果更好，每个源多取一些
        fetch_limit = max(limit * 2, 15) if (use_oa and use_any) else max(limit, 8)

        oa_papers: List[Paper] = []
        any_papers: List[Dict] = []

        # ---- 并行执行 ----
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = []

            if use_oa:
                futures.append(pool.submit(
                    self.openalex.search_papers,
                    query, limit=fetch_limit, sort=sort,
                    min_citations=min_citations,
                    year_from=year_from, year_to=year_to,
                    field_filter=field_filter,
                ))

            if use_any:
                futures.append(pool.submit(
                    self.anysearch.search_papers,
                    query, limit=fetch_limit,
                ))

            for future in as_completed(futures):
                try:
                    result = future.result(timeout=30)
                    if not result:
                        continue
                    if isinstance(result[0], Paper):
                        oa_papers = result
                    elif isinstance(result[0], dict):
                        any_papers = result
                except Exception as e:
                    print(f"[杂交] 并行搜索异常: {e}", file=sys.stderr)

        # ---- 融合与去重 ----
        return self._fuse(oa_papers, any_papers, final_limit=limit)

    # ------------------------------------------------------------------
    # 融合 / 去重 / 交叉验证
    # ------------------------------------------------------------------

    def _fuse(self, oa_papers: List[Paper], any_papers: List[Dict],
              final_limit: int) -> Dict[str, Any]:
        """融合两个源的结果，去重并标记交叉验证。"""

        # Step 1 — 用 DOI 建立索引
        oa_by_doi: Dict[str, Paper] = {}
        oa_no_doi: List[Paper] = []
        for p in oa_papers:
            if p.doi:
                oa_by_doi[p.doi.lower()] = p
            else:
                oa_no_doi.append(p)

        any_by_doi: Dict[str, Dict] = {}
        any_no_doi: List[Dict] = []
        for p in any_papers:
            doi = (p.get("doi") or "").lower()
            if doi:
                any_by_doi[doi] = p
            else:
                any_no_doi.append(p)

        # Step 2 — 交叉验证（DOI 匹配）
        cross: List[HybridPaper] = []
        all_dois: Set[str] = set(oa_by_doi.keys()) | set(any_by_doi.keys())

        for doi in all_dois:
            oa_p = oa_by_doi.get(doi)
            any_p = any_by_doi.get(doi)
            if oa_p and any_p:
                # 优先使用 OpenAlex 的结构化数据
                cross.append(HybridPaper(
                    title=oa_p.title,
                    authors=oa_p.authors,
                    year=oa_p.publication_year,
                    citations=oa_p.cited_by_count,
                    doi=doi,
                    abstract=oa_p.abstract,
                    sources=["openalex", "anysearch"],
                    venue=oa_p.venue or any_p.get("venue"),
                    volume=oa_p.volume or any_p.get("volume"),
                    issue=oa_p.issue or any_p.get("issue"),
                    pages=oa_p.pages or any_p.get("pages"),
                    url=oa_p.url or any_p.get("url"),
                ))

        # Step 3 — 非交叉部分（无 DOI 或单源）
        oa_only: List[HybridPaper] = []
        for p in oa_papers:
            key = (p.doi or "").lower()
            if key in any_by_doi:
                continue  # 已在 cross 中
            oa_only.append(HybridPaper(
                title=p.title,
                authors=p.authors,
                year=p.publication_year,
                citations=p.cited_by_count,
                doi=p.doi,
                abstract=p.abstract,
                sources=["openalex"],
                venue=p.venue,
                volume=p.volume,
                issue=p.issue,
                pages=p.pages,
                url=p.url,
            ))

        any_only: List[HybridPaper] = []
        for p in any_papers:
            key = (p.get("doi") or "").lower()
            if key in oa_by_doi:
                continue  # 已在 cross 中
            any_only.append(HybridPaper(
                title=p.get("title", "Unknown"),
                authors=p.get("authors", []),
                year=p.get("year"),
                citations=p.get("citations", 0),
                doi=p.get("doi"),
                abstract=p.get("abstract"),
                sources=["anysearch"],
                venue=p.get("venue"),
                volume=p.get("volume"),
                issue=p.get("issue"),
                pages=p.get("pages"),
                url=p.get("url"),
            ))

        # Step 4 — 标题模糊匹配（无 DOI 论文也必须进入交叉验证结果）
        fuzzy_cross, oa_only, any_only = self._fuzzy_dedup(oa_only, any_only)
        cross.extend(fuzzy_cross)

        # Step 5 — 按查询词覆盖率过滤，再以相关性优先、引用量次优排序。
        terms = self._query_terms(self._current_query)
        before_filter = len(cross) + len(oa_only) + len(any_only)
        cross = [paper for paper in cross if self._is_relevant(paper, terms)]
        oa_only = [paper for paper in oa_only if self._is_relevant(paper, terms)]
        any_only = [paper for paper in any_only if self._is_relevant(paper, terms)]
        filtered_irrelevant = before_filter - len(cross) - len(oa_only) - len(any_only)

        before_dedup = len(cross) + len(oa_only) + len(any_only)
        cross = self._dedup_titles(cross)
        oa_only = self._dedup_titles(oa_only)
        any_only = self._dedup_titles(any_only)
        collapsed_duplicates = before_dedup - len(cross) - len(oa_only) - len(any_only)

        rank = lambda paper: (self._relevance_score(paper, terms), paper.citations)
        cross.sort(key=rank, reverse=True)
        oa_only.sort(key=rank, reverse=True)
        any_only.sort(key=rank, reverse=True)

        # 先保留交叉验证结果，再按引用量从两个单源结果中补足名额。
        selected_cross = cross[:final_limit]
        remaining = max(0, final_limit - len(selected_cross))
        unique_pool = [
            ("openalex", paper) for paper in oa_only
        ] + [
            ("anysearch", paper) for paper in any_only
        ]
        unique_pool.sort(key=lambda item: rank(item[1]), reverse=True)
        selected = unique_pool[:remaining]
        selected_oa = [paper for source, paper in selected if source == "openalex"]
        selected_any = [paper for source, paper in selected if source == "anysearch"]

        return {
            "query": self._current_query,
            "cross_validated": selected_cross,
            "openalex_only": selected_oa,
            "anysearch_only": selected_any,
            "stats": {
                "openalex_total": len(oa_papers),
                "anysearch_total": len(any_papers),
                "cross_validated": len(cross),
                "openalex_unique": len(oa_only),
                "anysearch_unique": len(any_only),
                "filtered_irrelevant": filtered_irrelevant,
                "collapsed_duplicates": collapsed_duplicates,
            },
        }

    @staticmethod
    def _normalized_title(title: str) -> str:
        return " ".join(re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", title.lower()).split())

    @classmethod
    def _dedup_titles(cls, papers: List[HybridPaper]) -> List[HybridPaper]:
        chosen: Dict[str, HybridPaper] = {}
        for paper in papers:
            key = cls._normalized_title(paper.title) or paper.doi or paper.url or str(id(paper))
            current = chosen.get(key)
            if current is None or (paper.citations, bool(paper.abstract), bool(paper.venue)) > (
                current.citations, bool(current.abstract), bool(current.venue)
            ):
                chosen[key] = paper
        return list(chosen.values())

    @staticmethod
    def _query_terms(query: str) -> List[str]:
        """提取具有检索意义的词；连字符术语同时按组成词匹配。"""
        stopwords = {
            "a", "an", "and", "for", "in", "of", "on", "or", "the", "to", "with",
            "analysis", "based", "method", "model", "study", "using",
        }
        normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", query.lower())
        return [term for term in normalized.split() if term not in stopwords and len(term) > 1]

    @staticmethod
    def _paper_text(paper: HybridPaper) -> tuple[str, str]:
        title = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", paper.title.lower())
        detail = " ".join(filter(None, [paper.abstract, paper.venue])).lower()
        detail = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", detail)
        return f" {title} ", f" {detail} "

    @classmethod
    def _matched_terms(cls, paper: HybridPaper, terms: List[str]) -> Set[str]:
        title, detail = cls._paper_text(paper)
        return {
            term for term in terms
            if f" {term} " in title or f" {term} " in detail
        }

    @classmethod
    def _is_relevant(cls, paper: HybridPaper, terms: List[str]) -> bool:
        # 单个词可能是 AHP、PCA 等缩写，无法仅凭字面覆盖率安全淘汰结果。
        if len(terms) < 2:
            return True
        required = min(2, len(terms))
        return len(cls._matched_terms(paper, terms)) >= required

    @classmethod
    def _relevance_score(cls, paper: HybridPaper, terms: List[str]) -> int:
        title, detail = cls._paper_text(paper)
        return sum(
            3 if f" {term} " in title else 1 if f" {term} " in detail else 0
            for term in terms
        )

    def _fuzzy_dedup(self, oa_only: List[HybridPaper],
                     any_only: List[HybridPaper]) -> Tuple[List[HybridPaper], List[HybridPaper], List[HybridPaper]]:
        """把高度相似且年份相容的无 DOI 记录合并为交叉验证论文。"""
        def normalize(title: str) -> str:
            t = title.lower().strip()
            t = re.sub(r'[^\w\s]', '', t)
            return ' '.join(t.split())

        def overlap(a: str, b: str) -> float:
            words_a = set(normalize(a).split())
            words_b = set(normalize(b).split())
            if not words_a or not words_b:
                return 0.0
            return len(words_a & words_b) / max(len(words_a), len(words_b))

        # 检查 oa_only 中的标题与 any_only 中的标题
        kept_oa = list(oa_only)
        kept_any = list(any_only)
        cross: List[HybridPaper] = []

        for hp in oa_only:
            for ap in any_only:
                if hp.doi and ap.doi:
                    continue
                same_year = not hp.year or not ap.year or hp.year == ap.year
                if same_year and overlap(hp.title, ap.title) >= 0.85:
                    if hp in kept_oa:
                        kept_oa.remove(hp)
                    if ap in kept_any:
                        kept_any.remove(ap)
                    cross.append(HybridPaper(
                        title=hp.title,
                        authors=hp.authors or ap.authors,
                        year=hp.year or ap.year,
                        citations=max(hp.citations, ap.citations),
                        doi=hp.doi or ap.doi,
                        abstract=hp.abstract or ap.abstract,
                        sources=["openalex", "anysearch"],
                        venue=hp.venue or ap.venue,
                        volume=hp.volume or ap.volume,
                        issue=hp.issue or ap.issue,
                        pages=hp.pages or ap.pages,
                        url=hp.url or ap.url,
                    ))
                    break

        return cross, kept_oa, kept_any

    # ------------------------------------------------------------------
    # 展示
    # ------------------------------------------------------------------

    _current_query: str = ""

    def print_results(self, result: Dict[str, Any]):
        """打印可读的交叉验证结果。"""
        query = result.get("query", "")
        self._current_query = query  # stash for template
        stats = result["stats"]

        header = f"交叉验证搜索结果: {query}"
        print()
        print("=" * 60)
        print(f"  {header}")
        print("=" * 60)
        print(f"  数据源: OpenAlex + AnySearch")
        print(f"  统计: OpenAlex {stats['openalex_total']} 篇 | "
              f"AnySearch {stats['anysearch_total']} 篇 | "
              f"交叉验证 {stats['cross_validated']} 篇")
        print()

        # 交叉验证区域
        cross = result.get("cross_validated", [])
        if cross:
            self._print_section("交叉验证", "★", "OpenAlex + AnySearch 同时收录", cross, "verified")

        oa_only = result.get("openalex_only", [])
        if oa_only:
            self._print_section("OpenAlex 独有", "◆", "仅来自 OpenAlex", oa_only, "oa")

        any_only = result.get("anysearch_only", [])
        if any_only:
            self._print_section("AnySearch 独有", "◇", "仅来自 AnySearch", any_only, "any")

        if not cross and not oa_only and not any_only:
            print("  未找到相关论文。\n")

    _SECTION_COLORS = {
        "verified": "\033[33m",  # 金色
        "oa": "\033[36m",       # 青色
        "any": "\033[35m",      # 紫色
        "reset": "\033[0m",
    }
    # Windows 兼容：如果颜色不支持则静默降级
    _USE_COLOR = sys.platform != "win32" or os.environ.get("TERM", "").startswith("xterm")

    @classmethod
    def _c(cls, code: str) -> str:
        if cls._USE_COLOR:
            return cls._SECTION_COLORS.get(code, "")
        return ""

    def _print_section(self, title: str, icon: str, subtitle: str,
                       papers: List[HybridPaper], tag: str):
        c_tag = self._c(tag)
        c_reset = self._c("reset")

        print(f"  {c_tag}{icon} {title}{c_reset}")
        print(f"  {c_tag}  {subtitle}{c_reset}")
        print(f"  {c_tag}{'─' * 56}{c_reset}")

        for i, hp in enumerate(papers, 1):
            authors = ", ".join(hp.authors[:4])
            if len(hp.authors) > 4:
                authors += " et al."

            line = f"  [{i}] {hp.title}"
            print(f"  {c_tag}{line}{c_reset}")

            details = []
            if authors:
                details.append(f"作者: {authors}")
            if hp.year:
                details.append(f"年份: {hp.year}")
            if hp.citations:
                details.append(f"引用: {hp.citations}")
            if hp.doi:
                details.append(f"DOI: {hp.doi}")

            if details:
                print(f"     {' | '.join(details)}")
            if hp.abstract:
                preview = hp.abstract[:120].replace("\n", " ")
                print(f"     摘要: {preview}...")
            print()

        print()

    def results_to_json(self, result: Dict[str, Any]) -> str:
        """输出为 JSON。"""
        return json.dumps(result, ensure_ascii=False, indent=2,
                          default=self._json_default)

    @staticmethod
    def _json_default(obj):
        if isinstance(obj, HybridPaper):
            return obj.to_dict()
        if isinstance(obj, Paper):
            return obj.to_dict()
        return str(obj)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hybrid Scholar — 并行搜索 + 交叉验证 (OpenAlex + AnySearch)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 混合搜索（默认）
  python hybrid_scholar.py --query "grey prediction model"

  # 仅用 OpenAlex（传统模式）
  python hybrid_scholar.py --query "genetic algorithm" --openalex-only

  # 仅用 AnySearch
  python hybrid_scholar.py --query "reinforcement learning" --anysearch-only

  # 高级过滤 + 交叉验证
  python hybrid_scholar.py --query "TOPSIS" --min-citations 10 --year-from 2020 --field mathematics

  # JSON 输出
  python hybrid_scholar.py --query "LSTM" --json
        """,
    )
    parser.add_argument("--query", "-q", required=True, help="搜索关键词")
    parser.add_argument("--limit", "-n", type=int, default=8,
                        help="最终返回结果数量（默认 8）")
    parser.add_argument("--email", "-e",
                        help="OpenAlex 礼貌池邮箱（建议填写真实邮箱）")
    parser.add_argument("--anysearch-api-key",
                        help="AnySearch API Key（默认读取 ANYSEARCH_API_KEY 环境变量）")
    parser.add_argument("--sort", "-s",
                        choices=["relevance", "cited_by_count:desc",
                                 "cited_by_count:asc", "publication_year:desc",
                                 "publication_year:asc"],
                        default="relevance",
                        help="排序方式（仅 OpenAlex，默认相关性）")
    parser.add_argument("--min-citations", type=int,
                        help="最低引用量过滤（仅 OpenAlex）")
    parser.add_argument("--year-from", type=int,
                        help="起始年份（仅 OpenAlex）")
    parser.add_argument("--year-to", type=int,
                        help="结束年份（仅 OpenAlex）")
    parser.add_argument("--field",
                        choices=["mathematics", "computer_science", "engineering",
                                 "statistics", "operations_research", "physics", "economics"],
                        help="领域过滤（仅 OpenAlex）")
    parser.add_argument("--openalex-only", action="store_true",
                        help="仅使用 OpenAlex 搜索")
    parser.add_argument("--anysearch-only", action="store_true",
                        help="仅使用 AnySearch 搜索")
    parser.add_argument("--json", "-j", action="store_true",
                        help="以 JSON 格式输出")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    scholar = HybridScholar(
        email=args.email,
        anysearch_api_key=args.anysearch_api_key,
    )

    result = scholar.search_papers(
        query=args.query,
        limit=args.limit,
        sort=args.sort,
        min_citations=args.min_citations,
        year_from=args.year_from,
        year_to=args.year_to,
        field_filter=args.field,
        openalex_only=args.openalex_only,
        anysearch_only=args.anysearch_only,
    )

    if args.json:
        print(scholar.results_to_json(result))
    else:
        scholar.print_results(result)


if __name__ == "__main__":
    main()
