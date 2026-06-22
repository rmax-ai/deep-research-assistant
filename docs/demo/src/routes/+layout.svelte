<script>
  import { base } from "$app/paths";

  let { children } = $props();
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
        <strong>Deep Research Assistant Demo</strong>
        <small>Standalone streaming and inspection surface</small>
      </span>
    </a>
    <div class="nav-links">
      <a href="https://github.com/rmax-ai/deep-research-assistant">GitHub ↗</a>
    </div>
  </nav>
  <main>{@render children()}</main>
  <footer>
    <p>Deep Research Assistant Demo · Static SvelteKit frontend · Point it at a live API instance</p>
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
    --surface: rgba(255, 251, 244, 0.78);
    --text-strong: #16324f;
    --text-body: #4f6073;
    --text-soft: #7a695e;
    --line: rgba(22, 50, 79, 0.1);
    --accent: #d66f45;
    --accent-soft: #efb45b;
    --teal: #2d807f;
    --shadow: 0 22px 52px rgba(33, 46, 60, 0.08);
    --shell-width: 1040px;
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
    background: rgba(255, 252, 247, 0.82);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 1.1rem;
    overflow-x: auto;
    margin: 1rem 0;
    box-shadow: var(--shadow);
  }

  :global(pre code) {
    background: none;
    padding: 0;
    color: var(--text-strong);
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
    width: min(var(--shell-width), calc(100vw - 2rem));
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
  }

  .nav-links a:hover {
    color: var(--text-strong);
    background: rgba(255, 255, 255, 0.74);
    text-decoration: none;
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
