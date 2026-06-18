"""Unit tests for web search and retrieval tools."""



class TestWebSearch:
    async def test_search_returns_structured_results(self):
        """Verify search returns correct dict structure even on error."""
        from deep_research.tools.search import web_search

        result = await web_search("python programming", max_results=3)
        assert "query" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        assert result["query"] == "python programming"

    async def test_search_empty_query(self):
        """Verify empty query handling."""
        from deep_research.tools.search import web_search

        result = await web_search("")
        assert result["query"] == ""
        assert isinstance(result["results"], list)

    async def test_max_results_clamped(self):
        """Verify max_results is clamped to valid range."""
        from deep_research.tools.search import web_search

        result = await web_search("test", max_results=100)
        # Should be clamped to MAX_RESULTS (10)
        assert len(result["results"]) <= 10

    async def test_search_result_structure(self):
        """Verify each result has required fields."""
        from deep_research.tools.search import web_search

        result = await web_search("github.com", max_results=2)
        for item in result["results"]:
            assert "title" in item
            assert "url" in item
            assert "snippet" in item


class TestURLRetrieve:
    async def test_retrieve_returns_structured_results(self):
        """Verify retrieve returns correct dict structure."""
        from deep_research.tools.retrieval import url_retrieve

        result = await url_retrieve("https://example.com")
        assert "url" in result
        assert "title" in result
        assert "content" in result
        assert "content_length" in result
        assert "status_code" in result

    async def test_retrieve_invalid_url(self):
        """Verify invalid URL handling."""
        from deep_research.tools.retrieval import url_retrieve

        result = await url_retrieve("https://invalid.example.invalid")
        assert "error" in result or result["status_code"] == 0
        assert result["content_length"] == 0


class TestHTMLParsing:
    def test_strip_html(self):
        from deep_research.tools.search import _strip_html

        assert _strip_html("<b>Hello</b>") == "Hello"
        assert _strip_html('<a href="x">link</a>') == "link"
        assert _strip_html("no tags") == "no tags"

    def test_extract_between(self):
        from deep_research.tools.search import _extract_between

        result = _extract_between("startAAAendBBB", "start", "end")
        assert result == "AAA"

    def test_html_to_text(self):
        from deep_research.tools.retrieval import _html_to_text

        text = _html_to_text("<html><body><p>Hello</p><p>World</p></body></html>")
        assert "Hello" in text
        assert "World" in text
