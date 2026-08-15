#!/usr/bin/env python3
"""
OpenAlex Scholar - 学术论文搜索工具

通过 OpenAlex API 搜索学术论文，为数学建模提供参考文献支持。
支持按引用量、年份、领域过滤，以及多种排序方式。
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict


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


__all__ = ['Paper', 'OpenAlexScholar']


# OpenAlex 领域概念 ID（用于 field_filter）
FIELD_CONCEPTS = {
    'mathematics':    'https://api.openalex.org/concepts/C33923547',
    'computer_science': 'https://api.openalex.org/concepts/C41008148',
    'engineering':    'https://api.openalex.org/concepts/C127413603',
    'physics':        'https://api.openalex.org/concepts/C185592680',
    'statistics':     'https://api.openalex.org/concepts/C162324750',
    'operations_research': 'https://api.openalex.org/concepts/C126322002',
    'economics':      'https://api.openalex.org/concepts/C162111547',
}

FIELD_CONCEPT_ALIASES = {
    'math': 'mathematics',
    'cs': 'computer_science', 'computer': 'computer_science',
    'eng': 'engineering', 'engineer': 'engineering',
    'stats': 'statistics',
    'or': 'operations_research', '运筹': 'operations_research',
}


@dataclass
class Paper:
    """论文数据类"""
    title: str
    authors: List[str]
    publication_year: Optional[int]
    cited_by_count: int
    doi: Optional[str]
    abstract: Optional[str]
    source: str = "openalex"
    venue: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    first_page: Optional[str] = None
    last_page: Optional[str] = None
    url: Optional[str] = None

    @property
    def pages(self) -> Optional[str]:
        if self.first_page and self.last_page:
            return f"{self.first_page}-{self.last_page}"
        return self.first_page or self.last_page

    @property
    def citation_format(self) -> str:
        """生成引用格式 (APA 风格)"""
        author_str = ", ".join(self.authors[:3]) if self.authors else "Unknown"
        if len(self.authors) > 3:
            author_str += " et al."
        year_str = f" ({self.publication_year})" if self.publication_year else ""
        venue = f" {self.venue}" if self.venue else ""
        volume = f", {self.volume}" if self.volume else ""
        issue = f"({self.issue})" if self.issue else ""
        pages = f", {self.pages}" if self.pages else ""
        doi_str = f" https://doi.org/{self.doi}" if self.doi else ""
        return f"{author_str}{year_str}. {self.title}.{venue}{volume}{issue}{pages}.{doi_str}".strip()

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            'title': self.title,
            'authors': self.authors,
            'publication_year': self.publication_year,
            'cited_by_count': self.cited_by_count,
            'doi': self.doi,
            'abstract': self.abstract,
            'venue': self.venue,
            'volume': self.volume,
            'issue': self.issue,
            'pages': self.pages,
            'url': self.url,
            'citation_format': self.citation_format
        }


class OpenAlexScholar:
    """OpenAlex 学术搜索类"""

    # 合法的排序方式
    VALID_SORTS = {
        'relevance',              # 默认，不需要 sort 参数
        'cited_by_count:desc',    # 按引用量降序
        'cited_by_count:asc',     # 按引用量升序
        'publication_year:desc',  # 按年份降序（最新在前）
        'publication_year:asc',   # 按年份升序
    }

    def __init__(self, email: str = None):
        """
        初始化搜索器

        Args:
            email: 用于礼貌池的邮箱地址
        """
        self.base_url = "https://api.openalex.org/works"
        self.email = email

    def search_papers(
        self,
        query: str,
        limit: int = 8,
        page: int = 1,
        sort: str = 'relevance',
        min_citations: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        field_filter: Optional[str] = None,
    ) -> List[Paper]:
        """
        搜索论文

        Args:
            query: 搜索关键词
            limit: 每页返回结果数量 (1-200)
            page: 页码（从1开始）
            sort: 排序方式
                'relevance'          - 按相关性（默认）
                'cited_by_count:desc' - 按被引次数降序
                'cited_by_count:asc'  - 按被引次数升序
                'publication_year:desc' - 按年份降序
                'publication_year:asc'  - 按年份升序
            min_citations: 最低被引次数过滤
            year_from: 起始年份（包含）
            year_to: 结束年份（包含）
            field_filter: 领域过滤
                'mathematics' / 'computer_science' / 'engineering' /
                'statistics' / 'operations_research' / 'physics' / 'economics'

        Returns:
            论文列表
        """
        # 构建 OpenAlex API 请求参数
        params = {
            "search": query,
            "per_page": min(max(limit, 1), 200),
            "page": max(page, 1),
            "select": "id,display_name,authorships,cited_by_count,doi,publication_year,biblio,abstract_inverted_index,primary_location",
        }

        # 排序
        if sort and sort != 'relevance':
            if sort not in self.VALID_SORTS:
                print(f"警告: 不支持的排序方式 '{sort}'，将使用默认排序")
            else:
                params["sort"] = sort

        # 构建 filter 参数
        filters = []

        if min_citations is not None:
            filters.append(f"cited_by_count:>{min_citations - 1}")

        if year_from is not None and year_to is not None:
            filters.append(f"publication_year:{year_from}-{year_to}")
        elif year_from is not None:
            filters.append(f"publication_year:>{year_from - 1}")
        elif year_to is not None:
            filters.append(f"publication_year:<{year_to + 1}")

        if field_filter:
            resolved = self._resolve_field(field_filter)
            if resolved:
                filters.append(f"concept.id:{resolved}")
            else:
                print(f"警告: 不支持的领域 '{field_filter}'，可用值: {', '.join(FIELD_CONCEPTS.keys())}")

        if filters:
            params["filter"] = ",".join(filters)

        # 礼貌池
        if self.email:
            params["mailto"] = self.email

        query_string = urllib.parse.urlencode(params)
        url = f"{self.base_url}?{query_string}"

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        f"OpenAlexScholar (mailto:{self.email})"
                        if self.email else "OpenAlexScholar"
                    )
                }
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                return self._parse_results(data)

        except urllib.error.HTTPError as e:
            print(f"API 请求失败 (HTTP {e.code}): {e.reason}")
            if e.code == 403:
                print("提示: 请检查邮箱地址是否正确，或稍后重试")
            return []
        except urllib.error.URLError as e:
            print(f"网络连接失败: {e.reason}")
            print("提示: 请检查网络连接")
            return []
        except json.JSONDecodeError:
            print("API 返回数据格式异常")
            return []
        except Exception as e:
            print(f"搜索失败: {e}")
            return []

    def _resolve_field(self, field: str) -> Optional[str]:
        """解析领域名称到 OpenAlex Concept ID"""
        key = field.lower().strip()
        if key in FIELD_CONCEPT_ALIASES:
            key = FIELD_CONCEPT_ALIASES[key]
        return FIELD_CONCEPTS.get(key)

    def _parse_results(self, data: Dict) -> List[Paper]:
        """解析API返回结果"""
        papers = []
        results = data.get("results", [])

        for work in results:
            # 提取作者信息
            authors = []
            for authorship in work.get("authorships", []):
                author = authorship.get("author", {})
                author_name = author.get("display_name", "")
                if author_name:
                    authors.append(author_name)

            # 从倒排索引重建摘要
            abstract = None
            abstract_index = work.get("abstract_inverted_index")
            if abstract_index:
                abstract = self._get_abstract_from_index(abstract_index)

            biblio = work.get("biblio") or {}
            location = work.get("primary_location") or {}
            source_info = location.get("source") or {}
            paper = Paper(
                title=work.get("display_name", "Unknown Title"),
                authors=authors,
                publication_year=work.get("publication_year"),
                cited_by_count=work.get("cited_by_count", 0),
                doi=(
                    work.get("doi", "").replace("https://doi.org/", "")
                    if work.get("doi") else None
                ),
                abstract=abstract,
                source="openalex",
                venue=source_info.get("display_name"),
                volume=biblio.get("volume"),
                issue=biblio.get("issue"),
                first_page=biblio.get("first_page"),
                last_page=biblio.get("last_page"),
                url=location.get("landing_page_url"),
            )
            papers.append(paper)

        return papers

    def _get_abstract_from_index(self, abstract_inverted_index: Dict) -> str:
        """从倒排索引重建摘要"""
        try:
            max_position = max(
                max(positions) for positions in abstract_inverted_index.values()
            )
            words = [""] * (max_position + 1)

            for word, positions in abstract_inverted_index.items():
                for position in positions:
                    words[position] = word

            return " ".join(words).strip()
        except (ValueError, TypeError, KeyError):
            return ""


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="OpenAlex 学术论文搜索工具 — 支持多条件过滤和排序"
    )
    parser.add_argument("--query", "-q", required=True, help="搜索关键词")
    parser.add_argument("--email", "-e",
                        help="邮箱地址（用于礼貌池，建议填写真实邮箱）")
    parser.add_argument("--limit", "-n", type=int, default=8,
                        help="每页返回结果数量（默认8，最大200）")
    parser.add_argument("--page", "-p", type=int, default=1,
                        help="页码（从1开始，默认1）")
    parser.add_argument("--sort", "-s",
                        choices=["relevance", "cited_by_count:desc",
                                 "cited_by_count:asc", "publication_year:desc",
                                 "publication_year:asc"],
                        default="relevance",
                        help="排序方式（默认相关性）")
    parser.add_argument("--min-citations", type=int,
                        help="最低被引次数过滤")
    parser.add_argument("--year-from", type=int,
                        help="起始年份（包含）")
    parser.add_argument("--year-to", type=int,
                        help="结束年份（包含）")
    parser.add_argument("--field",
                        choices=list(FIELD_CONCEPTS.keys()),
                        help="领域过滤：mathematics / computer_science / engineering / statistics / operations_research / physics / economics")
    parser.add_argument("--json", "-j", action="store_true",
                        help="以JSON格式输出")

    args = parser.parse_args()

    print(f"正在搜索: {args.query}")
    if args.sort and args.sort != 'relevance':
        print(f"排序方式: {args.sort}")
    if args.min_citations:
        print(f"最低引用: {args.min_citations}")
    if args.year_from or args.year_to:
        print(f"年份范围: {args.year_from or '不限'} ~ {args.year_to or '不限'}")
    if args.field:
        print(f"领域限定: {args.field}")
    if args.email:
        print(f"邮箱: {args.email}")
    print("-" * 80)

    scholar = OpenAlexScholar(email=args.email)
    papers = scholar.search_papers(
        query=args.query,
        limit=args.limit,
        page=args.page,
        sort=args.sort,
        min_citations=args.min_citations,
        year_from=args.year_from,
        year_to=args.year_to,
        field_filter=args.field,
    )

    if not papers:
        print("未找到相关论文")
        return

    print(f"找到 {len(papers)} 篇相关论文:\n")

    for i, paper in enumerate(papers, 1):
        if args.json:
            print(json.dumps({
                "title": paper.title,
                "authors": paper.authors,
                "year": paper.publication_year,
                "citations": paper.cited_by_count,
                "doi": paper.doi,
                "abstract": (
                    paper.abstract[:200] + "..."
                    if paper.abstract and len(paper.abstract) > 200
                    else paper.abstract
                )
            }, ensure_ascii=False, indent=2))
        else:
            print(f"[{i}] {paper.title}")
            print(f"    作者: {', '.join(paper.authors[:5])}"
                  f"{' et al.' if len(paper.authors) > 5 else ''}")
            print(f"    年份: {paper.publication_year or 'Unknown'}")
            print(f"    引用: {paper.cited_by_count}")
            if paper.doi:
                print(f"    DOI: {paper.doi}")
            if paper.abstract:
                preview = paper.abstract[:150] + "..." if len(paper.abstract) > 150 else paper.abstract
                print(f"    摘要: {preview}")
            print()


if __name__ == "__main__":
    main()
