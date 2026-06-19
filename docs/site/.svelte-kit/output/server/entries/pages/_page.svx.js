import { s as sanitize_props, h as head, b as spread_props, a as attr } from "../../chunks/index.js";
import { D as DocLayout } from "../../chunks/DocLayout.js";
import { b as base } from "../../chunks/server.js";
import "../../chunks/url.js";
import "@sveltejs/kit/internal/server";
import "../../chunks/root.js";
const metadata = {
  "title": "Deep Research Assistant",
  "description": "Enterprise-grade governed AI research runtime"
};
const { title, description } = metadata;
function _page_svx($$renderer, $$props) {
  const $$sanitized_props = sanitize_props($$props);
  head("1l7f6wk", $$renderer, ($$renderer2) => {
    $$renderer2.title(($$renderer3) => {
      $$renderer3.push(`<title>Deep Research Assistant</title>`);
    });
    $$renderer2.push(`<meta name="description" content="Enterprise-grade governed AI research runtime built on Google ADK 2.0" class="svelte-1l7f6wk"/>`);
  });
  DocLayout($$renderer, spread_props([
    $$sanitized_props,
    metadata,
    {
      children: ($$renderer2) => {
        $$renderer2.push(`<div class="hero svelte-1l7f6wk"><div class="pulse svelte-1l7f6wk"></div> <h1 class="svelte-1l7f6wk">Deep Research Assistant</h1> <p class="subtitle svelte-1l7f6wk">Enterprise-grade governed AI research runtime</p> <p class="desc svelte-1l7f6wk">Converts broad research requests into governed, inspectable, and reproducible research workflows.
    Built on <strong class="svelte-1l7f6wk">Google ADK 2.0</strong> with a STORM-inspired multi-agent pipeline.</p> <div class="ctas svelte-1l7f6wk"><a${attr("href", base + "/architecture/")} class="btn primary svelte-1l7f6wk">Architecture</a> <a href="https://github.com/rmax-ai/deep-research-assistant" class="btn secondary svelte-1l7f6wk">GitHub</a></div></div> <div class="features svelte-1l7f6wk"><div class="feature-card svelte-1l7f6wk"><div class="icon cyan svelte-1l7f6wk">◇</div> <h3 class="svelte-1l7f6wk">Evidence-First Pipeline</h3> <p class="svelte-1l7f6wk">Intent → scope → perspectives → questions → search → evidence → claims → contradictions → outline → drafts → verification → report.
      Every claim is traceable to source excerpts.</p></div> <div class="feature-card svelte-1l7f6wk"><div class="icon emerald svelte-1l7f6wk">◆</div> <h3 class="svelte-1l7f6wk">STORM-Grade Iteration</h3> <p class="svelte-1l7f6wk">Evidence-conditioned follow-up questions, frontier scheduling with priority scoring,
      information-gain metrics, and a Research Moderator that detects stagnation.</p></div> <div class="feature-card svelte-1l7f6wk"><div class="icon violet svelte-1l7f6wk">⬡</div> <h3 class="svelte-1l7f6wk">Governed by Default</h3> <p class="svelte-1l7f6wk">Identity propagation, policy engine with role-based tool allowlists, immutable audit log,
      approval gates at semantic boundaries. Designed for enterprise from day one.</p></div></div> <div class="stats svelte-1l7f6wk"><div class="stat svelte-1l7f6wk"><div class="stat-num svelte-1l7f6wk">46</div> <div class="stat-label svelte-1l7f6wk">Stories across 7 phases</div></div> <div class="stat svelte-1l7f6wk"><div class="stat-num svelte-1l7f6wk">82+</div> <div class="stat-label svelte-1l7f6wk">Tests passing</div></div> <div class="stat svelte-1l7f6wk"><div class="stat-num svelte-1l7f6wk">14</div> <div class="stat-label svelte-1l7f6wk">LLM Agents</div></div> <div class="stat svelte-1l7f6wk"><div class="stat-num svelte-1l7f6wk">30</div> <div class="stat-label svelte-1l7f6wk">Workflow Nodes</div></div></div> <div class="phase-grid svelte-1l7f6wk"><h2 class="svelte-1l7f6wk">Implementation Phases</h2> <div class="phase-row done svelte-1l7f6wk"><span class="svelte-1l7f6wk">0</span> Architecture Spike</div> <div class="phase-row done svelte-1l7f6wk"><span class="svelte-1l7f6wk">1</span> Evidence-First MVP</div> <div class="phase-row done svelte-1l7f6wk"><span class="svelte-1l7f6wk">2</span> STORM-Grade Iterative Research</div> <div class="phase-row done svelte-1l7f6wk"><span class="svelte-1l7f6wk">3</span> Co-STORM Collaboration</div> <div class="phase-row done svelte-1l7f6wk"><span class="svelte-1l7f6wk">4</span> Epistemic Reliability</div> <div class="phase-row done svelte-1l7f6wk"><span class="svelte-1l7f6wk">5</span> Enterprise Governance</div> <div class="phase-row done svelte-1l7f6wk"><span class="svelte-1l7f6wk">6</span> Continuous Research</div></div>`);
      },
      $$slots: { default: true }
    }
  ]));
}
export {
  _page_svx as default,
  metadata
};
