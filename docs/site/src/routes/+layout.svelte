<script>
  import { afterNavigate } from "$app/navigation";
  import { base } from "$app/paths";
  import { onMount, tick } from "svelte";

  let { children } = $props();

  const COPY_RESET_DELAY_MS = 1600;

  function resetButtonLabel(button) {
    window.setTimeout(() => {
      button.disabled = false;
      button.textContent = "Copy";
    }, COPY_RESET_DELAY_MS);
  }

  async function writeToClipboard(text) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }

    const fallback = document.createElement("textarea");
    fallback.value = text;
    fallback.setAttribute("readonly", "true");
    fallback.style.position = "absolute";
    fallback.style.left = "-9999px";
    document.body.append(fallback);
    fallback.select();
    document.execCommand("copy");
    fallback.remove();
  }

  function enhanceCodeBlocks() {
    for (const pre of document.querySelectorAll("article.doc pre")) {
      if (pre.dataset.copyEnhanced === "true") {
        continue;
      }

      const button = document.createElement("button");
      button.type = "button";
      button.className = "copy-code-button";
      button.textContent = "Copy";
      button.addEventListener("click", async () => {
        const code = pre.querySelector("code")?.textContent?.replace(/\n$/, "") ?? "";
        button.disabled = true;

        try {
          await writeToClipboard(code);
          button.textContent = "Copied";
        } catch {
          button.textContent = "Failed";
        }

        resetButtonLabel(button);
      });

      pre.dataset.copyEnhanced = "true";
      pre.append(button);
    }
  }

  onMount(() => {
    const applyEnhancements = async () => {
      await tick();
      enhanceCodeBlocks();
    };

    void applyEnhancements();
    afterNavigate(() => {
      void applyEnhancements();
    });
  });
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;700&display=swap"
    rel="stylesheet"
  />
</svelte:head>

<div class="app">
  <nav class="top-nav">
    <a href={base + "/"} class="logo">
      <span class="logo-mark">DR</span>
      <span class="logo-copy">
        <strong>Deep Research Assistant</strong>
        <small>Governed multi-agent research runtime</small>
      </span>
    </a>
    <div class="nav-links">
      <a href={base + "/architecture/"}>Architecture</a>
      <a href={base + "/phases/"}>Phases</a>
      <a href={base + "/api/"}>API</a>
      <a href="https://github.com/rmax-ai/deep-research-assistant" class="gh-link">GitHub ↗</a>
    </div>
  </nav>
  <main>{@render children()}</main>
  <footer>
    <p>Deep Research Assistant · MIT License · Built with ADK 2.0 + SvelteKit</p>
  </footer>
</div>

<style>
  :global(*) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  :global(:root) {
    --page-bg: #f5efe4;
    --page-bg-strong: #efe3d2;
    --surface: rgba(255, 251, 244, 0.78);
    --surface-strong: rgba(255, 255, 255, 0.84);
    --shell-width: 1120px;
    --shell-gutter: 1rem;
    --doc-width: 800px;
    --text-strong: #16324f;
    --text-body: #4f6073;
    --text-soft: #7a695e;
    --line: rgba(22, 50, 79, 0.1);
    --accent: #d66f45;
    --accent-soft: #efb45b;
    --teal: #2d807f;
    --shadow: 0 22px 52px rgba(33, 46, 60, 0.08);
  }

  :global(body) {
    font-family: "Inter", system-ui, sans-serif;
    background:
      radial-gradient(circle at top left, rgba(239, 180, 91, 0.2), transparent 32%),
      radial-gradient(circle at top right, rgba(45, 128, 127, 0.16), transparent 28%),
      linear-gradient(180deg, #f7f0e4 0%, #f4ebdf 44%, #f8f4ee 100%);
    color: var(--text-strong);
    line-height: 1.6;
    min-height: 100vh;
  }

  :global(h1, h2, h3, h4, h5, h6) {
    font-family: "Space Grotesk", "Inter", sans-serif;
    font-weight: 700;
  }

  :global(code) {
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.875em;
    background: rgba(22, 50, 79, 0.07);
    padding: 0.15em 0.4em;
    border-radius: 6px;
    color: var(--teal);
  }

  :global(pre) {
    position: relative;
    background: rgba(255, 252, 247, 0.82);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 2.85rem 1.1rem 1.1rem;
    overflow-x: auto;
    margin: 1rem 0;
    box-shadow: var(--shadow);
  }

  :global(pre code) {
    display: block;
    background: none;
    padding: 0;
    color: var(--text-strong);
  }

  :global(.copy-code-button) {
    position: absolute;
    top: 0.8rem;
    right: 0.8rem;
    border: 1px solid rgba(22, 50, 79, 0.16);
    border-radius: 999px;
    padding: 0.35rem 0.75rem;
    background: rgba(255, 255, 255, 0.9);
    color: var(--text-body);
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }

  :global(.copy-code-button:hover:enabled) {
    background: rgba(255, 255, 255, 1);
    color: var(--text-strong);
    border-color: rgba(22, 50, 79, 0.24);
  }

  :global(.copy-code-button:disabled) {
    cursor: default;
    opacity: 0.78;
  }

  :global(a) {
    color: var(--accent);
    text-decoration: none;
  }

  :global(a:hover) {
    text-decoration: underline;
  }

  :global(ul, ol) {
    padding-left: 1.5rem;
    margin: 0.5rem 0;
  }

  :global(li) {
    margin: 0.25rem 0;
  }

  :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 1rem 0;
    background: rgba(255, 252, 247, 0.7);
    border-radius: 18px;
    overflow: hidden;
  }

  :global(th) {
    text-align: left;
    background: rgba(22, 50, 79, 0.05);
    padding: 0.5rem 1rem;
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.8rem;
    color: var(--text-soft);
    border-bottom: 1px solid var(--line);
  }

  :global(td) {
    padding: 0.5rem 1rem;
    border-bottom: 1px solid var(--line);
    font-size: 0.875rem;
  }

  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  .top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    width: min(var(--shell-width), calc(100% - (var(--shell-gutter) * 2)));
    margin: 0 auto;
    padding: 1rem 0;
    border-bottom: 1px solid var(--line);
    background: rgba(250, 245, 236, 0.72);
    backdrop-filter: blur(12px);
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .logo {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    color: var(--text-strong) !important;
    text-decoration: none !important;
  }

  .logo-mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.4rem;
    height: 2.4rem;
    border-radius: 0.8rem;
    background: linear-gradient(135deg, var(--accent), var(--accent-soft));
    color: white;
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.9rem;
    font-weight: 700;
    box-shadow: 0 12px 24px rgba(214, 111, 69, 0.24);
  }

  .logo-copy {
    display: grid;
    gap: 0.05rem;
  }

  .logo-copy strong {
    font-size: 0.96rem;
    color: var(--text-strong);
  }

  .logo-copy small {
    color: var(--text-soft);
    font-size: 0.72rem;
    letter-spacing: 0.02em;
  }

  .nav-links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.8rem;
    align-items: center;
  }

  .nav-links a {
    padding: 0.55rem 0.8rem;
    border-radius: 999px;
    font-size: 0.84rem;
    font-weight: 500;
    color: var(--text-body);
    text-decoration: none;
    transition: color 0.15s, background 0.15s;
  }

  .nav-links a:hover {
    color: var(--text-strong);
    background: rgba(255, 255, 255, 0.74);
    text-decoration: none;
  }

  .gh-link {
    color: var(--accent) !important;
    font-family: "IBM Plex Mono", monospace;
    font-size: 0.8rem;
  }

  main {
    flex: 1;
  }

  footer {
    text-align: center;
    padding: 2rem;
    font-size: 0.75rem;
    color: var(--text-soft);
    border-top: 1px solid var(--line);
    font-family: "IBM Plex Mono", monospace;
    background: rgba(255, 251, 244, 0.45);
  }

  @media (max-width: 820px) {
    .top-nav {
      align-items: start;
      flex-direction: column;
    }
  }
</style>
