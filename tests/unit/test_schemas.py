"""Tests for core schema models."""


from deep_research.schemas import (
    ApprovalDecision,
    ApprovalGate,
    Claim,
    ClaimType,
    Contradiction,
    DepthLevel,
    EpistemicStatus,
    EvidenceFragment,
    EvidenceType,
    InferenceOperation,
    InferenceStep,
    Outline,
    OutlineSection,
    OutputType,
    Perspective,
    QuestionGraph,
    QuestionOrigin,
    QuestionType,
    ResearchMode,
    ResearchObjective,
    ResearchQuestion,
    ResearchRun,
    RunStatus,
    SearchPlan,
    SectionDraft,
    SourceRecord,
    StoppingDecision,
    VerificationFinding,
    VerificationSeverity,
)
from deep_research.schemas.scope import (
    Assumption,
    Definition,
    ResearchScope,
    RiskLevel,
    SourceType,
    TimeRange,
)


class TestResearchObjective:
    def test_minimal(self):
        obj = ResearchObjective(title="Test", primary_question="What is X?")
        assert obj.title == "Test"
        assert obj.output_type == OutputType.TECHNICAL_REPORT
        assert obj.desired_depth == DepthLevel.STANDARD

    def test_invalid_title_empty(self):
        # Pydantic v2 accepts empty strings by default — min_length must be explicit
        obj = ResearchObjective(title="", primary_question="What is X?")
        assert obj.title == ""

    def test_all_fields(self):
        obj = ResearchObjective(
            title="Security Analysis",
            primary_question="What are the threats?",
            decision_to_support="Choose runtime",
            intended_audience=["architects"],
            output_type=OutputType.RISK_MEMO,
            desired_depth=DepthLevel.DEEP,
            language="de",
        )
        assert obj.decision_to_support == "Choose runtime"
        assert len(obj.intended_audience) == 1


class TestResearchRun:
    def test_minimal(self):
        obj = ResearchObjective(title="T", primary_question="Q?")
        run = ResearchRun(run_id="r1", user_id="u1", objective=obj)
        assert run.status == RunStatus.DRAFT
        assert run.mode == ResearchMode.REVIEW_FIRST
        assert run.scope is None

    def test_with_scope(self):
        obj = ResearchObjective(title="T", primary_question="Q?")
        scope = ResearchScope(included_topics=["security"])
        run = ResearchRun(run_id="r1", user_id="u1", objective=obj, scope=scope)
        assert run.scope.included_topics == ["security"]


class TestResearchScope:
    def test_defaults(self):
        scope = ResearchScope()
        assert scope.included_topics == []
        assert scope.risk_level == RiskLevel.MEDIUM

    def test_with_constraints(self):
        scope = ResearchScope(
            included_topics=["auth", "sandbox"],
            excluded_topics=["pricing"],
            required_dimensions=["security", "performance"],
            risk_level=RiskLevel.HIGH,
        )
        assert len(scope.included_topics) == 2
        assert scope.risk_level == RiskLevel.HIGH


class TestPerspective:
    def test_minimal(self):
        p = Perspective(perspective_id="arch", name="Architecture", purpose="Analyze system design")
        assert p.perspective_id == "arch"
        assert p.budget_weight == 1.0

    def test_with_source_types(self):
        p = Perspective(
            perspective_id="sec",
            name="Security",
            purpose="Threat analysis",
            preferred_source_types=[SourceType.OFFICIAL_DOCUMENTATION, SourceType.STANDARD],
            required_checks=["STRIDE", "attack_tree"],
            prohibited_actions=["modify_evidence"],
        )
        assert len(p.preferred_source_types) == 2
        assert "STRIDE" in p.required_checks


class TestResearchQuestion:
    def test_minimal(self):
        q = ResearchQuestion(
            question_id="q1", text="What is ADK?", question_type=QuestionType.DEFINITIONAL
        )
        assert q.status.value == "pending"
        assert q.priority == 0.5

    def test_with_parents(self):
        q = ResearchQuestion(
            question_id="q2",
            text="How does ADK handle auth?",
            question_type=QuestionType.MECHANISTIC,
            parent_question_ids=["q1"],
            origin=QuestionOrigin.EVIDENCE_CONDITIONED,
        )
        assert q.parent_question_ids == ["q1"]

    def test_question_graph(self):
        q1 = ResearchQuestion(
            question_id="q1", text="What is X?", question_type=QuestionType.DEFINITIONAL
        )
        q2 = ResearchQuestion(
            question_id="q2", text="How does X work?", question_type=QuestionType.MECHANISTIC
        )
        graph = QuestionGraph(run_id="r1", questions={"q1": q1, "q2": q2})
        assert len(graph.questions) == 2


class TestSearchPlan:
    def test_minimal(self):
        plan = SearchPlan(question_id="q1", objective="Find X documentation")
        assert plan.queries == []
        assert plan.max_results == 50

    def test_with_queries(self):
        from deep_research.schemas.search import SearchQuery

        plan = SearchPlan(
            question_id="q1",
            objective="Find docs",
            queries=[
                SearchQuery(
                    query_id="sq1", raw_query="ADK security docs", strategy="official_docs"
                ),
            ],
            freshness_requirement="last_year",
        )
        assert len(plan.queries) == 1


class TestSourceRecord:
    def test_minimal(self):
        src = SourceRecord(source_id="s1", canonical_uri="https://example.com/doc")
        assert src.source_type == SourceType.OTHER

    def test_with_authority(self):
        from deep_research.schemas.source import AuthorityClass, SourcePolicyStatus

        src = SourceRecord(
            source_id="s1",
            canonical_uri="https://example.com",
            title="Official Docs",
            publisher="Example Inc",
            source_type=SourceType.OFFICIAL_DOCUMENTATION,
            authority_class=AuthorityClass.HIGH,
            trust_score=0.9,
            policy_status=SourcePolicyStatus.ACCEPTED,
        )
        assert src.authority_class == AuthorityClass.HIGH


class TestEvidenceFragment:
    def test_basic(self):
        ev = EvidenceFragment(
            evidence_id="e1",
            source_id="s1",
            exact_excerpt="ADK supports tool governance.",
            evidence_type=EvidenceType.API_SPECIFICATION,
        )
        assert ev.exact_excerpt == "ADK supports tool governance."

    def test_with_qualifiers(self):
        ev = EvidenceFragment(
            evidence_id="e2",
            source_id="s1",
            exact_excerpt="The system supports up to 100 concurrent users.",
            qualifiers=["tested on v2.0", "single-region only"],
            confidence=0.7,
        )
        assert len(ev.qualifiers) == 2


class TestClaim:
    def test_minimal(self):
        c = Claim(claim_id="c1", text="ADK supports tool governance")
        assert c.epistemic_status == EpistemicStatus.EXTRACTED
        assert c.confidence == 0.5

    def test_with_inference(self):
        c = Claim(
            claim_id="c2",
            text="ADK is suitable for enterprise deployments",
            claim_type=ClaimType.CAUSAL,
            epistemic_status=EpistemicStatus.INFERRED,
            evidence_ids=["e1", "e2"],
            inference_steps=[
                InferenceStep(
                    premise_claim_ids=["c1"],
                    operation=InferenceOperation.INDUCTION,
                    conclusion_claim_id="c2",
                    rationale="Tool governance is a prerequisite for enterprise use",
                    model_id="gemini-2.5-pro",
                ),
            ],
            confidence=0.6,
            qualifiers=["assuming standard enterprise requirements"],
        )
        assert len(c.inference_steps) == 1
        assert c.inference_steps[0].operation == InferenceOperation.INDUCTION


class TestContradiction:
    def test_basic(self):
        from deep_research.schemas.contradiction import ContradictionType, ResolutionStatus

        ct = Contradiction(
            contradiction_id="ct1",
            claim_ids=["c1", "c2"],
            contradiction_type=ContradictionType.DIRECT_FACTUAL_CONFLICT,
            explanation="Source A says X, Source B says Y",
        )
        assert ct.resolution_status == ResolutionStatus.UNRESOLVED


class TestOutline:
    def test_basic(self):
        ol = Outline(
            outline_id="ol1",
            run_id="r1",
            sections=[
                OutlineSection(section_id="s1", title="Introduction"),
                OutlineSection(
                    section_id="s2",
                    title="Architecture",
                    parent_id="s1",
                    required_claim_ids=["c1", "c2"],
                ),
            ],
        )
        assert len(ol.sections) == 2
        assert ol.sections[1].parent_id == "s1"


class TestSectionDraft:
    def test_basic(self):
        d = SectionDraft(section_id="s1", content="## Introduction\n\nThis is the intro.")
        assert d.status == "draft"

    def test_blocked(self):
        from deep_research.schemas.draft import MissingClaim

        d = SectionDraft(
            section_id="s2",
            status="blocked",
            blocked_reason="Missing evidence for production adoption",
            missing_claims=[
                MissingClaim(
                    description="Evidence for production-scale adoption is missing",
                    recommended_question="What independently documented production deployments exist?",
                ),
            ],
        )
        assert d.status == "blocked"
        assert len(d.missing_claims) == 1


class TestVerificationFinding:
    def test_blocking(self):
        vf = VerificationFinding(
            finding_id="vf1",
            severity=VerificationSeverity.BLOCKING,
            description="Claim C5 has no evidence link",
            affected_claim_ids=["c5"],
        )
        assert vf.severity == VerificationSeverity.BLOCKING


class TestApprovalDecision:
    def test_basic(self):
        ad = ApprovalDecision(
            approval_id="a1",
            run_id="r1",
            gate=ApprovalGate.SCOPE,
            decision="approved",
            approver_id="u1",
        )
        assert ad.gate == ApprovalGate.SCOPE


class TestStoppingDecision:
    def test_not_stopping(self):
        sd = StoppingDecision(should_stop=False, reasons=["still finding new evidence"])
        assert not sd.should_stop

    def test_stopping(self):
        sd = StoppingDecision(
            should_stop=True,
            reasons=["all material questions resolved", "primary source threshold met"],
            primary_source_coverage=0.8,
            contradiction_resolution_rate=0.9,
        )
        assert sd.should_stop
        assert sd.primary_source_coverage == 0.8


class TestTimeRange:
    def test_basic(self):
        from datetime import date

        tr = TimeRange(start=date(2024, 1, 1), end=date(2024, 12, 31))
        assert tr.start.year == 2024

    def test_open_ended(self):
        tr = TimeRange(start=None, end=None)
        assert tr.start is None


class TestAssumption:
    def test_basic(self):
        a = Assumption(text="The system uses ADK 2.0", risk_if_wrong=RiskLevel.HIGH)
        assert a.risk_if_wrong == RiskLevel.HIGH


class TestDefinition:
    def test_basic(self):
        d = Definition(
            term="Agent", definition="A bounded LLM worker with specific tools and mandate"
        )
        assert d.term == "Agent"
