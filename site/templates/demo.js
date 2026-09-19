(function(){
  const TYPE_MS_PER_CHAR = 28;

  function escape(s){
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  const TOPBAR = {
    fresh:'alpi v0.3.0 <span class="sep">·</span> <span class="lbl">profile </span><span class="acc">default</span> <span class="sep">·</span> sandbox off <span class="sep">·</span> ~/projects/alpi',
    work: 'alpi v0.3.0 <span class="sep">·</span> <span class="lbl">profile </span><span class="acc">work</span> <span class="sep">·</span> sandbox off <span class="sep">·</span> ~/projects/work',
    personal:'alpi v0.3.0 <span class="sep">·</span> <span class="lbl">profile </span><span class="acc">reviewer</span> <span class="sep">·</span> sandbox on <span class="sep">·</span> /srv/agents',
  };
  const STATUS = {
    fresh:'<span class="diamond">◆</span> deepseek-v4.1-flash <span class="sep">·</span> ctx 8.4K/1M <span class="sep">·</span> $0.00',
    hero: '<span class="diamond">◆</span> deepseek-v4.1-flash <span class="sep">·</span> ctx 24K/1M <span class="sep">·</span> $0.01',
  };
  const PLACEHOLDER = 'Type a message or /help for commands…';

  const TOOL_PAD = 14;
  function pad(s){
    let n = TOOL_PAD - s.length;
    return n > 0 ? s + " ".repeat(n) : s;
  }
  function tool(name, args, result, dur){
    return `<span class="diamond">◆</span> <span class="tool">${pad(name)}</span> <span class="muted">${args}</span>  <span class="muted">→</span>  ${result}` +
      (dur ? `   <span class="muted">${dur}</span>` : "");
  }

  const HERO_SCENES = [
    {
      kind:"chat",
      topbar: TOPBAR.personal,
      statusbar: STATUS.hero,
      placeholder: PLACEHOLDER,
      initialBody:"",
      turns:[
        {
          input:"what landed overnight, and what needs me before standup?",
          lines:[
            { d:300, t: tool("schedule", "list · today",          '<span class="muted">3 jobs ran</span>') },
            { d:380, t: tool("memory",   "read · review notes",   '<span class="muted">2 open threads</span>') },
            { d:360, t: tool("peer",     "link.ask · librarian",  '<span class="muted">changelog diff</span>') },
            { d:240, t:"" },
            { d:320, t:'<span class="bot">Nightly pipeline finished clean. The migration job retried once and settled.</span>' },
            { d:160, t:'<span class="bot">PR #412 needs you: the retry state is not reset after a timeout.</span>' },
            { d:160, t:'<span class="bot">Spend is $6.10 of the $20 daily cap on this profile. The librarian bills its own.</span>' },
          ],
          postPause: 1400,
        },
        {
          input:"ask builder to review the payment PR before standup",
          lines:[
            { d:320, t: tool("peer", "link.ask · builder", '<span class="muted">PR review</span>') },
            { d:520, t: tool("todo", "add Check the retry reset path", '<span class="muted">0. [ ] Check the retry reset path</span>') },
            { d:280, t:"" },
            { d:360, t:'<span class="bot">@builder found one real issue: retry state is not reset after timeout.</span>' },
            { d:160, t:'<span class="bot">It left a minimal patch and a focused test. Everything else is cosmetic.</span>' },
          ],
          postPause: 1500,
        },
        {
          input:"post the decision to #launch and notify the phone if anyone blocks",
          lines:[
            { d:480, t: tool("workgroup_post", "wg_id=wg_7x2f9kq3", '<span class="muted">posted seq 184 · declared $0.0031</span>', "0.2s") },
            { d:420, t: tool("notify", "text=Ping me if anyone blocks…", '<span class="muted">delivered: alpi</span>') },
            { d:420, t:'<span class="bot">posted. If a profile flags a blocker, desktop and mobile will show the same thread.</span>' },
          ],
          postPause: 1700,
        },
      ],
      loop:true,
      hideNav:true,
      hideStepHeader:true,
    },
  ];

  const QUICKSTART_SCENES = [
    {
      id:1, title:"Install",
      cmd:"uv tool install alpi-agent",
      kind:"shell",
      output:`Resolved 89 packages in 1.2s
<span class="ok">Installed</span> alpi-agent v0.3.0 <span class="muted">·</span> 1 executable: alpi`,
      caption:"Single command. Python 3.11–3.13. The browser tool downloads the Chromium headless shell (~340 MB) the first time it runs — no separate install step."
    },
    {
      id:2, title:"Pick a model",
      cmd:"alpi setup",
      kind:"wizard",
      topbar:'alpi <span class="muted">·</span> setup <span class="sep">·</span> <span class="lbl">profile </span><span class="acc">default</span>',
      output:`<span class="muted">  ↑↓ select   ⏎ confirm   esc back</span>

  <span class="muted">Agent</span>
  <span class="acc">› Model / Provider</span>        <span class="muted">(not set)</span>
    Routing models              <span class="muted">(not set — everything runs on the main model)</span>
    Voice                       <span class="muted">Aria (en-US)</span>
    MCPs                        <span class="muted">none</span>
    Emails                      <span class="muted">none</span>

  <span class="muted">Boundaries</span>
    Workspace                   <span class="muted">not set · falls back to cwd</span>
    Sandbox                     <span class="muted">off</span>
    Budget                      <span class="muted">unlimited</span>

  <span class="muted">ALP (Alpi Link Protocol)</span>
    Identity                    <span class="muted">not set · peers see handle only</span>
    Peers                       <span class="muted">none pinned</span>
    Workgroups                  <span class="muted">none</span>
    Peer TCP listener           <span class="muted">auto:7423 (Noise_XK)</span>

  <span class="muted">Services</span>
    Daemon                      <span class="muted">not installed</span>
    Schedules                   <span class="muted">no jobs</span>
    Connections                 <span class="muted">ready</span>

  <span class="muted">Maintenance</span>
    Health check                <span class="muted">open to run checks</span>
    Cleanup                     <span class="muted">nothing to clean</span>`,
      caption:"Fresh profiles ship with no default — pick provider, paste key, choose model. See MODELS for tiered guidance."
    },
    {
      id:3, title:"Pin a workspace",
      cmd:"alpi setup → Workspace",
      kind:"wizard",
      topbar:'alpi <span class="muted">·</span> setup <span class="sep">›</span> workspace <span class="sep">·</span> <span class="lbl">profile </span><span class="acc">default</span>',
      output:`  <span class="muted">Default root for relative paths in file tools.</span>
  <span class="muted">Empty = falls back to cwd at launch.</span>

  <span class="acc">› Workspace directory:</span> ~/projects/alpi<span class="alpi-cursor"></span>

  <span class="check">✓</span> workspace set to /Users/you/projects/alpi`,
      caption:"Same wizard, Workspace. Point it at the dir alpi may read/write. Fallback is cwd at launch — fine for trying, not for real use."
    },
    {
      id:4, title:"Send a message",
      cmd:"alpi",
      kind:"chat",
      topbar: TOPBAR.fresh,
      statusbar: STATUS.fresh,
      placeholder: PLACEHOLDER,
      initialBody:"",
      turns:[
        {
          input:"what can you see in this workspace?",
          lines:[
            { d:320, t: tool("search", "files · README", '<span class="muted">3 matches</span>') },
            { d:360, t: tool("read_file", "README.md", '<span class="muted">8.4 KB</span>') },
            { d:240, t:"" },
            { d:300, t:'<span class="bot">This looks like an alpi workspace: Python package, docs, site templates, and app clients.</span>' },
            { d:160, t:'<span class="bot">I\'ll treat relative paths as rooted here unless you tell me otherwise.</span>' },
          ],
          postPause: 900,
        },
        {
          input:"remember that i prefer short direct answers",
          lines:[
            { d:400, t: tool("memory", "add USER.md  prefers short direct a…", '<span class="muted">Added 1 entry in USER.md.</span>') },
            { d:240, t:"" },
            { d:280, t:'<span class="bot">Noted. I\'ll keep replies concise unless the task needs detail.</span>' },
          ],
          postPause: 1500,
        },
      ],
      loop:false,
      caption:"Type your first message. The useful first test is workspace awareness; the second is memory. Slash commands to try next: /help · /memory · /skills · /status · /new · /model."
    },
    {
      id:5, title:"Ask alpi about itself",
      cmd:"alpi",
      kind:"chat",
      topbar: TOPBAR.fresh,
      statusbar: STATUS.fresh,
      placeholder: PLACEHOLDER,
      initialBody:"",
      turns:[
        {
          input:"what is ALP and how do peers stay private?",
          lines:[
            { d:320, t: tool("alpi_knowledge", "action=index", '<span class="muted">15 topics</span>') },
            { d:520, t: tool("alpi_knowledge", "action=view", '<span class="muted">alp — pinned identity, signed envelopes, w…</span>') },
            { d:280, t:"" },
            { d:340, t:'<span class="bot">ALP is the Alpi Link Protocol — how alpis talk to each other.</span>' },
            { d:160, t:'<span class="bot">  · ALP.1 over Unix sockets (same machine).</span>' },
            { d:160, t:'<span class="bot">  · ALP.2 over Noise_XK TCP (across machines).</span>' },
            { d:160, t:'<span class="bot">  · ALP.3 adds shared workgroups.</span>' },
            { d:240, t:'<span class="bot">Every envelope is Ed25519-signed. Peers are pinned by pubkey —</span>' },
            { d:140, t:'<span class="bot">no discovery service, no central registry.</span>' },
          ],
          postPause: 1500,
        },
      ],
      loop:false,
      caption:"alpi ships the `alpi_knowledge` tool. Ask about config, commands, profiles, skills, or ALP and it answers from the packaged references without hitting the web."
    },
    {
      id:6, title:"Connect email",
      cmd:"alpi setup → Email",
      kind:"wizard",
      topbar:'alpi <span class="muted">·</span> setup <span class="sep">›</span> email <span class="sep">·</span> <span class="lbl">profile </span><span class="acc">default</span>',
      output:`  <span class="muted">↑↓ select   ⏎ configure   esc back</span>

  <span class="acc">› IMAP</span>         <span class="check">✓</span> connected
    Gmail        <span class="muted">not configured</span>

  <span class="muted">───────────────────────────────────────────────</span>

  <span class="check">✓</span> Daemon installed: <span class="acc">com.alpi.daemon</span>
  <span class="check">✓</span> Listening · pid 86403`,
      caption:"Optional. Connect email (IMAP / Gmail) if you want the agent reading and sending mail. The primary surfaces are the terminal, desktop, and mobile apps over the daemon."
    },
    {
      id:7, title:"Check health",
      cmd:"alpi doctor",
      kind:"shell",
      output:`alpi 0.3.0 <span class="muted">·</span> profile: <span class="acc">default</span>

<span class="muted">Version</span>
  <span class="check">✓</span> alpi-agent           v0.3.0 <span class="muted">(latest)</span>

<span class="muted">Model</span>
  <span class="check">✓</span> configured           openrouter/deepseek/deepseek-v4.1-flash
  <span class="check">✓</span> API key              OPENROUTER_API_KEY set

<span class="muted">Workspace</span>
  <span class="check">✓</span> ready                /Users/you/projects/alpi

<span class="muted">Email</span>
  <span class="check">✓</span> Email                you@example.com · IMAP

<span class="muted">Services</span>
  <span class="check">✓</span> Service              running · pid 86403

<span class="muted">ALP</span>
  <span class="check">✓</span> Identity             Ed25519 keypair present
  <span class="check">✓</span> Socket               listening on alp.sock

<span class="check">✓</span> all checks passed`,
      caption:"Live checks: model reachable, email accounts reachable, MCP handshaking, services alive, ALP socket listening, peers reachable. Exits 1 on any failure — cron-friendly. The basics are working — what follows is optional growth."
    },
    {
      id:8, title:"Add a second profile",
      cmd:"alpi profile create work",
      kind:"shell",
      output:`<span class="check">✓</span> profile <span class="acc">'work'</span> created at ~/.alpi/profiles/work/

$ alpi -p work setup
  <span class="muted">AGENT</span>
  <span class="acc">› Model / Provider</span>        <span class="muted">(not set)</span>
    Voice                       <span class="muted">—</span>
    MCPs                        <span class="muted">0 servers</span>

  <span class="muted">BOUNDARIES</span>
    Workspace                   <span class="muted">not set</span>
    Sandbox                     <span class="muted">off</span>
    ...`,
      caption:"Optional. Different API key, different memory, different bot, different identity. Fully isolated under ~/.alpi/profiles/work/. Useful when you want to keep work and personal completely apart."
    },
    {
      id:9, title:"Link another alpi",
      cmd:"alpi -p work peers add alice <PUBKEY>",
      kind:"shell",
      output:`<span class="check">✓</span> peer <span class="acc">'alice'</span> pinned (Ed25519)

$ alpi -p work peers ping alice
<span class="check">✓</span> alice replied in 12ms

$ alpi -p work workgroup join alice wg_stack-decision
<span class="check">✓</span> joined <span class="acc">#stack-decision</span> · 2 members`,
      caption:"Optional. The same Service install above already exposes the ALP listener — pin pubkeys with alpi setup → ALP → Peers. ALP.2 for machine links, ALP.3 workgroups when several alpis need a shared workspace."
    }
  ];

  const SCENE_SETS = {
    quickstart: QUICKSTART_SCENES,
    hero: HERO_SCENES,
  };

  function frameSkeleton(showCaption){
    return `
      <div class="alpi-term">
        <div class="alpi-term-top">
          <div class="left"></div>
          <div class="right"></div>
        </div>
        <div class="alpi-term-body"></div>
        <div class="alpi-term-status" hidden></div>
        <div class="alpi-term-input" hidden></div>
        <div class="alpi-term-foot">
          <span><button data-act="restart" type="button">↻ restart</button></span>
          <span class="nav">
            <button data-act="prev" type="button">← prev</button>
            <button data-act="next" type="button">next →</button>
          </span>
        </div>
      </div>` +
      (showCaption ? `<p class="alpi-term-caption"></p>` : "");
  }

  function topbarLeft(scene, idx, total){
    if(scene.hideStepHeader){
      return scene.topbar
        ? `<span class="topinfo">${scene.topbar}</span>`
        : "";
    }
    const stepLabel = `step ${String(scene.id || idx+1).padStart(2,"0")} · ${escape(scene.title || "")}`;
    return `<span class="step">${stepLabel}</span>`;
  }
  function topbarRight(scene, idx, total){
    if(scene.hideStepHeader){
      return "";
    }
    return `<span class="of">${idx+1} / ${total}</span>`;
  }

  function bodyForOutputScene(scene){
    let head = "";
    if(scene.topbar){
      head = `<span class="muted">${scene.topbar}</span>\n\n`;
    }
    return `<span class="alpi-cmd">${escape(scene.cmd)}</span>\n` +
      head + scene.output +
      `<span class="alpi-cursor idle"></span>`;
  }

  function bodyForChatScene(scene){
    return scene.initialBody || "";
  }

  function mountDemo(node){
    if(node._mounted) return;
    node._mounted = true;
    node.classList.add("alpi-demo");

    const setName = node.dataset.sceneSet || "quickstart";
    const SCENES = SCENE_SETS[setName] || QUICKSTART_SCENES;
    const TOTAL = SCENES.length;
    const showCaption = setName !== "hero";

    node.innerHTML = frameSkeleton(showCaption);

    const tbLeft  = node.querySelector(".alpi-term-top .left");
    const tbRight = node.querySelector(".alpi-term-top .right");
    const body    = node.querySelector(".alpi-term-body");
    const statusbar = node.querySelector(".alpi-term-status");
    const inputBar  = node.querySelector(".alpi-term-input");
    const foot      = node.querySelector(".alpi-term-foot");
    const cap       = node.querySelector(".alpi-term-caption");
    const btnPrev = node.querySelector('[data-act="prev"]');
    const btnNext = node.querySelector('[data-act="next"]');
    const btnRestart = node.querySelector('[data-act="restart"]');

    let idx = 0;
    let timers = [];
    let cancelled = false;

    function clearTimers(){
      cancelled = true;
      timers.forEach(t => clearTimeout(t));
      timers = [];
    }
    function later(fn, ms){
      const t = setTimeout(() => {
        if(!cancelled) fn();
      }, ms);
      timers.push(t);
    }
    function reset(){
      cancelled = false;
      timers = [];
    }

    function setStatusbar(scene){
      if(scene.statusbar){
        statusbar.innerHTML = scene.statusbar;
        statusbar.hidden = false;
      } else {
        statusbar.hidden = true;
      }
    }
    function setInputBar(scene, html){
      if(scene.kind === "chat" || scene.placeholder){
        inputBar.innerHTML = html != null
          ? html
          : `<span class="prompt">›</span> <span class="placeholder">${escape(scene.placeholder || PLACEHOLDER)}</span>`;
        inputBar.hidden = false;
      } else {
        inputBar.hidden = true;
      }
    }
    function setNav(scene){
      if(scene.hideNav || TOTAL <= 1){
        foot.hidden = true;
      } else {
        foot.hidden = false;
        btnPrev.disabled = idx === 0;
        btnNext.disabled = idx === TOTAL - 1;
      }
    }
    function setHeader(scene){
      tbLeft.innerHTML  = topbarLeft(scene, idx, TOTAL);
      tbRight.innerHTML = topbarRight(scene, idx, TOTAL);
    }

    function appendLine(html){
      body.insertAdjacentHTML("beforeend", html + "\n");
      body.scrollTop = body.scrollHeight;
    }

    async function typeIntoInput(scene, text){
      const promptHtml = `<span class="prompt">›</span> <span class="typed"></span><span class="alpi-cursor"></span>`;
      inputBar.innerHTML = promptHtml;
      const typedSpan = inputBar.querySelector(".typed");
      let pos = 0;
      return new Promise(resolve => {
        const tick = () => {
          if(cancelled) return resolve();
          if(pos < text.length){
            typedSpan.textContent = text.slice(0, ++pos);
            later(tick, TYPE_MS_PER_CHAR);
          } else {
            later(resolve, 380);
          }
        };
        tick();
      });
    }

    async function playChatScene(scene){
      body.innerHTML = bodyForChatScene(scene);

      const runOnce = async () => {
        for(let ti = 0; ti < scene.turns.length; ti++){
          const turn = scene.turns[ti];
          if(cancelled) return;
          await typeIntoInput(scene, turn.input);
          if(cancelled) return;
          setInputBar(scene);
          if(body.innerHTML.length > 0){
            appendLine("");
          }
          appendLine(`<span class="prompt">›</span> <span class="user">${escape(turn.input)}</span>`);
          appendLine("");
          for(const line of turn.lines){
            await new Promise(r => later(r, line.d));
            if(cancelled) return;
            appendLine(line.t);
          }
          if(turn.postPause){
            await new Promise(r => later(r, turn.postPause));
          }
        }
      };

      await runOnce();
      if(scene.loop && !cancelled){
        await new Promise(r => later(r, 1800));
        if(!cancelled){
          playChatScene(scene);
        }
      }
    }

    function playOutputScene(scene){
      const cmd = scene.cmd || "";
      let pos = 0;
      body.innerHTML = `<span class="alpi-cmd"></span><span class="alpi-cursor"></span>`;
      const cmdSpan = body.querySelector(".alpi-cmd");

      const onSkip = () => { clearTimers(); reset(); body.innerHTML = bodyForOutputScene(scene); };
      body.addEventListener("click", onSkip, { once:true });

      const tick = () => {
        if(cancelled) return;
        if(pos < cmd.length){
          cmdSpan.textContent = cmd.slice(0, ++pos);
          later(tick, TYPE_MS_PER_CHAR);
        } else {
          later(() => {
            body.removeEventListener("click", onSkip);
            body.innerHTML = bodyForOutputScene(scene);
          }, 240);
        }
      };
      tick();
    }

    function render(){
      clearTimers(); reset();
      const scene = SCENES[idx];
      setHeader(scene);
      setStatusbar(scene);
      setInputBar(scene);
      setNav(scene);
      if(showCaption && cap){ cap.textContent = scene.caption || ""; }

      if(scene.kind === "chat"){
        playChatScene(scene);
      } else {
        playOutputScene(scene);
      }
    }

    btnPrev.addEventListener("click", () => { if(idx>0){ idx--; render(); }});
    btnNext.addEventListener("click", () => { if(idx<TOTAL-1){ idx++; render(); }});
    btnRestart.addEventListener("click", () => { idx = 0; render(); });

    render();
  }

  function bindToggle(toggleNode, gridNode, demoNode){
    const buttons = toggleNode.querySelectorAll("button[data-mode]");
    function setMode(mode){
      buttons.forEach(b => b.setAttribute("aria-pressed", b.dataset.mode === mode ? "true" : "false"));
      if(mode === "console"){
        gridNode.hidden = true;
        demoNode.hidden = false;
        mountDemo(demoNode);
      } else {
        gridNode.hidden = false;
        demoNode.hidden = true;
      }
    }
    buttons.forEach(b => b.addEventListener("click", () => setMode(b.dataset.mode)));
  }

  function init(){
    document.querySelectorAll("[data-alpi-demo]").forEach(node => {
      const toggleSel = node.dataset.toggleWith;
      const gridSel = node.dataset.gridSel;
      const toggleNode = toggleSel ? document.querySelector(toggleSel) : null;
      const gridNode = gridSel ? document.querySelector(gridSel) : null;
      if(toggleNode && gridNode){
        node.hidden = true;
        bindToggle(toggleNode, gridNode, node);
      } else {
        mountDemo(node);
      }
    });
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
