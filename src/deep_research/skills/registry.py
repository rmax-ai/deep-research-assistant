"""Research Skill Registry — internal abstraction over ADK skills.

Progressive disclosure: list shows name + description + trigger conditions only.
Full instructions load only after selection.
"""

from __future__ import annotations

from typing import Any, TypedDict


class SkillMetadata(TypedDict):
    skill_id: str
    name: str
    version: str
    description: str
    trigger_conditions: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class LoadedSkill(TypedDict):
    skill_id: str
    version: str
    instructions: str
    allowed_tools: list[str]
    prohibited_tools: list[str]
    required_checks: list[str]
    maximum_budget: dict[str, int]
    templates: dict[str, Any]


# Skill templates (progressive disclosure: metadata only until loaded)
_SKILL_TEMPLATES: dict[str, dict[str, Any]] = {
    "technical_architecture_analysis": {
        "name": "Technical Architecture Analysis",
        "version": "1.0.0",
        "description": "Analyzes system architecture, trust boundaries, and component interactions.",
        "trigger_conditions": ["objective contains 'architecture'", "domain is technical"],
        "instructions": "Decompose the target system: identify components, trust boundaries, data flows, and failure modes.",
        "default_perspectives": ["architecture", "security", "operations", "failure_modes"],
        "required_question_types": ["mechanistic", "implementation", "security", "failure_mode"],
        "preferred_source_types": ["primary", "technical_report", "standard"],
        "quality_checks": ["primary_source_minimum", "contradiction_search", "temporal_validity"],
        "budget_recommendations": {"searches": 30, "sources": 15, "tokens": 80000},
    },
    "security_threat_analysis": {
        "name": "Security Threat Analysis",
        "version": "1.0.0",
        "description": "Analyzes threat actors, attack surfaces, controls, and residual risk.",
        "trigger_conditions": ["objective contains 'security'", "objective contains 'threat'"],
        "instructions": "Identify assets, threat actors, attack paths, preventive controls, and residual risk.",
        "default_perspectives": ["security", "architecture", "operations", "skeptical"],
        "required_question_types": ["security", "failure_mode", "counterfactual", "comparative"],
        "preferred_source_types": ["primary", "standard", "academic", "expert_analysis"],
        "quality_checks": ["primary_source_minimum", "contradiction_search", "counter_evidence"],
        "budget_recommendations": {"searches": 40, "sources": 20, "tokens": 100000},
    },
    "standards_analysis": {
        "name": "Standards Analysis",
        "version": "1.0.0",
        "description": "Analyzes compliance with standards, regulations, and industry frameworks.",
        "trigger_conditions": ["objective contains 'standard'", "objective contains 'compliance'"],
        "instructions": "Map the target against relevant standards, identify gaps, and recommend remediation.",
        "default_perspectives": ["standards", "operations", "legal_regulatory", "implementation"],
        "required_question_types": ["normative", "comparative", "descriptive", "definitional"],
        "preferred_source_types": ["standard", "official", "primary"],
        "quality_checks": ["primary_source_minimum", "temporal_validity"],
        "budget_recommendations": {"searches": 25, "sources": 12, "tokens": 70000},
    },
    "vendor_claim_validation": {
        "name": "Vendor Claim Validation",
        "version": "1.0.0",
        "description": "Validates vendor claims against independent sources and real-world evidence.",
        "trigger_conditions": ["objective contains 'vendor'", "objective contains 'compare'"],
        "instructions": "Cross-reference vendor claims with independent sources. Flag unsupported claims.",
        "default_perspectives": ["skeptical", "implementation", "comparative", "architecture"],
        "required_question_types": ["comparative", "counterfactual", "evidence_challenge", "quantitative"],
        "preferred_source_types": ["primary", "academic", "expert_analysis", "technical_report"],
        "quality_checks": ["contradiction_search", "counter_evidence", "source_independence"],
        "budget_recommendations": {"searches": 35, "sources": 15, "tokens": 90000},
    },
    "executive_brief_generation": {
        "name": "Executive Brief Generation",
        "version": "1.0.0",
        "description": "Generates concise executive summaries with confidence indicators and decision support.",
        "trigger_conditions": ["output_type is 'executive_brief'", "audience includes 'executive'"],
        "instructions": "Produce a concise executive synthesis: material findings, confidence levels, risk indicators.",
        "default_perspectives": ["enterprise_implications", "risk", "cost_benefit"],
        "required_question_types": ["normative", "comparative", "quantitative"],
        "preferred_source_types": ["primary", "expert_analysis", "technical_report"],
        "quality_checks": ["confidence_tracking", "recommendation_traceability"],
        "budget_recommendations": {"searches": 15, "sources": 8, "tokens": 40000},
    },
}


class ResearchSkillRegistry:
    """Internal abstraction over ADK skills with progressive disclosure."""

    def __init__(self) -> None:
        self._usage_log: list[dict[str, Any]] = []

    def list_skills(self, context: dict[str, Any] | None = None) -> list[SkillMetadata]:
        """List available skills with metadata only (progressive disclosure)."""
        _ = context
        return [
            {
                "skill_id": sid,
                "name": s["name"],
                "version": s["version"],
                "description": s["description"],
                "trigger_conditions": s.get("trigger_conditions", []),
                "input_schema": {},
                "output_schema": {},
            }
            for sid, s in _SKILL_TEMPLATES.items()
        ]

    def load_skill(self, skill_id: str, version: str = "latest") -> LoadedSkill | None:
        """Load full skill instructions. Only after selection by user/system."""
        template = _SKILL_TEMPLATES.get(skill_id)
        if not template:
            return None
        return {
            "skill_id": skill_id,
            "version": template["version"],
            "instructions": template["instructions"],
            "allowed_tools": template.get("allowed_tools", ["web_search", "url_retrieve"]),
            "prohibited_tools": template.get("prohibited_tools", ["production_write_tools"]),
            "required_checks": template.get("quality_checks", []),
            "maximum_budget": template.get("budget_recommendations", {}),
            "templates": {
                "default_perspectives": template.get("default_perspectives", []),
                "required_question_types": template.get("required_question_types", []),
                "preferred_source_types": template.get("preferred_source_types", []),
            },
        }

    def authorize_skill(self, principal: dict[str, Any], skill_id: str) -> bool:
        """Check if principal is authorized to use a skill."""
        # All skills are authorized for now (policy engine handles tool access)
        _ = principal
        return skill_id in _SKILL_TEMPLATES

    def record_usage(self, run_id: str, skill_id: str, version: str) -> None:
        """Record skill usage for audit."""
        self._usage_log.append({
            "run_id": run_id,
            "skill_id": skill_id,
            "version": version,
            "used_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
        })

    def get_usage_log(self) -> list[dict[str, Any]]:
        return list(self._usage_log)


# Singleton
_registry: ResearchSkillRegistry | None = None


def get_skill_registry() -> ResearchSkillRegistry:
    global _registry
    if _registry is None:
        _registry = ResearchSkillRegistry()
    return _registry
