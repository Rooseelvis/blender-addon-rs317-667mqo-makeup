# blender-addon-rs317-667mqo-makeup
RSPS TOOLKIT is a powerful Blender addon designed for RuneScape Private Server (RSPS) developers.
It streamlines model creation, weighting, PMN texturing, priority/TSKIN painting,
Aether material tinting, and seamless export/import for 317/OSRS and 667 formats. Perfect for turning Blender meshes int




<html>
<body>
<!--StartFragment--><h1 dir="auto">RSPS TOOLKIT User Guide</h1>
<p dir="auto" style="white-space: pre-wrap;">Welcome to <strong>RSPS TOOLKIT v7.7.0</strong>—your all-in-one Blender powerhouse for RuneScape Private Server (RSPS) model development! Tailored for Blender 4.5+, this addon transforms raw meshes into polished, game-ready .dat files with effortless automation. From skeletal weighting and procedural texturing to priority painting and color tinting, it covers the full RS workflow for 317/OSRS classics and 667-era models.</p>
<p dir="auto" style="white-space: pre-wrap;">Whether you're crafting epic player gear, quirky NPCs, or wild custom assets, RSPS TOOLKIT slashes tedious tasks by auto-generating essential data layers (VSKIN, RSPRI, RSTSKIN) and delivering stunning real-time visualizations. Dive in and level up your RSPS creations!</p>
<h2 dir="auto">Key Features at a Glance</h2>

<div><div><div></div></div><div dir="auto" style="mask-image: linear-gradient(to right, black 85%, transparent 100%); mask-composite: add;"><div style="height: 100%; width: 1px; left: 0px; flex-shrink: 0;"></div>
Feature | What It Does | Why You'll Love It
-- | -- | --
Model Weighter | VSKIN vertex weighting with body-part presets & mirroring | Quick skeletal setups—no more manual bone painting!
Priority Painter | RSPRI face priorities (0-255) for render depth | Perfect overlays for transparent effects like capes.
TSKIN Painter | RSTSKIN texture groups for multi-layer sorting | Seamless texture stacking with material-matched colors.
PMN Texturing | Procedural UVs with PMN projections & looping animations | Auto-sync UVs to textures; supports cylindrical/spherical modes.
Aether Materials | RGB/HSV tinting, UV-sampling, & alpha control | Dynamic recolors + randomization for endless variations.
Exporter | .dat exports with auto-type detection & drop variants | One-click normal + _drop.dat files for inventory bliss.
Importers | 317/OSRS & 667 .dat loading with full reconstruction | Brings legacy models to life, textures included (via texture_dump).
Visualizations | Overlays for weights, priorities, TSKINs, & UV arrows | Real-time feedback—see changes as you tweak.
RS-Style Render | Cel-shaded viewport setup | Preview your models in authentic RuneScape vibes.

<div style="height: 100%; width: 1px; right: 0px; flex-shrink: 0;"></div></div></div>
<p dir="auto" style="white-space: pre-wrap;">The toolkit lives in the 3D Viewport's N-Panel under the <strong>RSPS ADDON</strong> tab. Pro tip: Drop your textures into a <span>texture_dump</span> folder next to your .blend file (or addon dir) for instant loading—name 'em like <span>PMN_1.png</span> for PMN magic.</p>
<h2 dir="auto">System Specs</h2>
<ul dir="auto">
<li><strong>Blender</strong>: 4.5.0+ (battle-tested on 4.5.2).</li>
<li><strong>OS</strong>: Windows (optimized), macOS/Linux (solid support).</li>
<li><strong>Hardware</strong>: Any decent GPU for silky overlays (NVIDIA/AMD shine here).</li>
<li><strong>Dependencies</strong>: Zero—pure Blender builtins (bmesh, gpu, mathutils).</li>
</ul>
<h2 dir="auto">Installation: Get Up &amp; Running in Minutes</h2>
<ol dir="auto">
<li><strong>Grab the Goods</strong>:
<ul dir="auto">
<li>Unzip the download or snag the folder with all .py files (<span>__init__.py</span>, <span>dat_exporter.py</span>, <span>weighter.py</span>, etc.).</li>
</ul>
</li>
<li><strong>Hunt Down Addons Folder</strong>:
<ul dir="auto">
<li><strong>Windows</strong>: <span>C:\Users\[YourUsername]\AppData\Roaming\Blender Foundation\Blender\4.5\scripts\addons</span></li>
<li><strong>macOS</strong>: <span>~/Library/Application Support/Blender/4.5/scripts/addons</span></li>
<li><strong>Linux</strong>: <span>~/.config/blender/4.5/scripts/addons</span></li>
<li><em>Swap <span>4.5</span> for your Blender version.</em></li>
</ul>
</li>
<li><strong>Drop It In</strong>:
<ul dir="auto">
<li>Paste the full folder (e.g., <span>rsps_toolkit</span>) into <span>addons</span>. Keep files nested—no flattening!</li>
</ul>
</li>
<li><strong>Activate</strong>:
<ul dir="auto">
<li>Fire up Blender 4.5+.</li>
<li>Hit <strong>Edit &gt; Preferences &gt; Add-ons</strong>.</li>
<li>Search "RSPS TOOLKIT" and tick the box.</li>
<li>Restart if Blender acts shy.</li>
</ul>
</li>
<li><strong>Test Drive</strong>:
<ul dir="auto">
<li>New scene &gt; 3D Viewport &gt; <span>N</span> key for sidebar.</li>
<li>Spot <strong>RSPS ADDON</strong>? You're golden! 🎉</li>
</ul>
</li>
</ol>
<p dir="auto" style="white-space: pre-wrap;"><strong>Trouble Shooting?</strong></p>
<ul dir="auto">
<li>Addon ghosting? Double-check Blender version (Help &gt; About). Fresh reinstall FTW.</li>
<li>Console gremlins? Window &gt; Toggle System Console (Windows) for debug deets.</li>
<li>Textures AWOL? Brew a <span>texture_dump</span> folder by your .blend, toss in PNGs/JPGs (e.g., <span>PMN_1.png</span>).</li>
</ul>
<h2 dir="auto">Workflow: From Sketch to Server-Ready</h2>
<ol dir="auto">
<li><strong>Import Base</strong> (Opt.): File &gt; Import &gt; Pick 317/OSRS or 667 Model to suck in a .dat.</li>
<li><strong>Weight It Up</strong>: Tab to Edit Mode, lasso vertices, slap on Weighter presets.</li>
<li><strong>Texture &amp; Tag</strong>: Layer PMN textures, paint priorities/TSKINs on faces.</li>
<li><strong>Color Pop</strong>: Aether panel for tints, alphas, and that fresh glow.</li>
<li><strong>Ship Out</strong>: Object Mode &gt; Set export dir &gt; Smash Export DAT.</li>
<li><strong>Eyeball It</strong>: Crank visualizations for instant vibes-checks.</li>
</ol>
<p dir="auto" style="white-space: pre-wrap;">Ready to roll? Let's break it down section by section.</p>
<h2 dir="auto">1. Model Weighter: Bone Up Your Rigs</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> Slaps VSKIN weights (layers 1-3) on vertices for buttery RS animations. Stored as vertex groups (Blender 0-1, exports 0-100).</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Grab a mesh &gt; Tab to <strong>Edit Mode</strong>.</li>
<li><strong>RSPS ADDON &gt; Epic Model Weighter</strong>:
<ul dir="auto">
<li><strong>Layer Up</strong>: "Create V1/V2/V3" for VSKIN groups.</li>
<li><strong>Preset Power</strong>: Lasso verts (e.g., noggin), hit buttons like "Skull" (1.000 weight).
<ul dir="auto">
<li><em>Hits</em>: Head/Neck, Torso/Arms, Gloves, Legs/Boots, Extras (Sword/Shield/Necklace).</li>
</ul>
</li>
<li><strong>DIY Dose</strong>: Dial "Custom Weight" (0-1) &gt; "Assign Custom".</li>
</ul>
</li>
<li><strong>Full Monty Mirror</strong>: Select half-model (+X) &gt; "Create &amp; Apply Mirror" (<em>Destructive—save a copy!</em>).</li>
<li><strong>Peek Mode</strong>: "Show Weight Values" overlays digits; flip layers via slider.</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>Auto-splits totals &gt;1 across layers (e.g., 1.5 = 1.0 V1 + 0.5 V2).</li>
<li>Half-model first, mirror second—exporter sniffs types (e.g., HEAD via {1,2,3} weights).</li>
</ul>
<h2 dir="auto">2. Priority Painter: Depth Masterclass</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> Vertex-color RSPRI (0-255) for face draw order—high values front-and-center.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Mesh select &gt; <strong>Edit Mode</strong>.</li>
<li><strong>RSPS ADDON &gt; Priority Painter</strong>:
<ul dir="auto">
<li>Crank "Priority Value" (default 10).</li>
<li>Face-select &gt; "Apply to Selected Faces" (spawns RSPRI layer).</li>
</ul>
</li>
<li><strong>Viz It</strong>: "Priority Intensity" (0-1) for hue-shifted overlays (<em>Tweak <span>materials.py</span> for custom palettes</em>).
<ul dir="auto">
<li>Low-to-high sort; labels pop on centers.</li>
</ul>
</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>Ideal for see-throughs (e.g., capes at 200+).</li>
<li>"Test Material Loading" for color sanity-check.</li>
</ul>
<h2 dir="auto">3. TSKIN Painter: Texture Tango</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> RSTSKIN groups (0-255) sort multi-tex layers like a boss.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Echo Priorities: Mesh &gt; Edit &gt; <strong>TSKIN Painter</strong>.
<ul dir="auto">
<li>Set "TSKIN Group".</li>
<li>Faces &gt; "Apply to Selected Faces" (RSTSKIN layer).</li>
</ul>
</li>
<li><strong>Viz It</strong>: "TSKIN Intensity" for material-tinted glows.</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>0=base, 1=overlay—exporter packs 'em if present.</li>
<li>Same debug button for color vibes.</li>
</ul>
<h2 dir="auto">4. PMN Texturing: UV Wizardry Unleashed</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> Crafts RS-procedural textures via PMN (Projection/Mapping/Normal) with auto-UVs and timeline loops.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Mesh &gt; <strong>Edit Mode</strong> &gt; <strong>PMN Texturing</strong>:
<ul dir="auto">
<li><strong>Pick Pic</strong>: Dropdown from <span>texture_dump</span> (e.g., PMN_*.png).</li>
<li><strong>Slap It On</strong>: Faces &gt; "Apply Texture &amp; Create UVs" (solo) or "Multi Texturing" (per-mat).
<ul dir="auto">
<li>Nodes go REPEAT—boom, materials minted.</li>
</ul>
</li>
<li><strong>Tweak Time</strong>:
<ul dir="auto">
<li>"Start Auto Sync" for live PMN updates on UV fiddles.</li>
<li>Edit Mode &gt; "Manual Sync (Current Selection)".</li>
<li><strong>Transforms</strong>: Offset/Scale U/V &gt; "Capture Current".</li>
<li><strong>Animate</strong>: "↕ Animate Vertically" for driver-fueled loops; "Stop" to halt.</li>
</ul>
</li>
</ul>
</li>
<li><strong>Viz It</strong>: "Show PMN Visualization" arrows trace UV flow.</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>PMN vectors per-mat; 667 importer handles fancy projections (cyl/sphere).</li>
<li><span>texture_dump</span>: PMN_1.png = ID 1—easy peasy.</li>
</ul>
<h2 dir="auto">5. Aether Materials: Hue &amp; Cry</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> RGB/HSV recolors, texture-sampling, &amp; alpha finesse for vibrant variants.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li>Multi-mesh OK &gt; <strong>Aether Color Tint</strong>:
<ul dir="auto">
<li><strong>UV Magic</strong>: "Select Texture" samples colors to new mats.</li>
<li><strong>Preset Party</strong>: Buttons for "Red"/"Blue" etc. (<em>Hack <span>aether_materials.py</span> PRESETS</em>).</li>
<li><strong>Sliders</strong>: R/G/B or H/S/V—hits all selected.
<ul dir="auto">
<li>"Apply Original" / "Reset" for backups.</li>
<li>"Randomize (Varied)" = chaos mode.</li>
</ul>
</li>
<li><strong>Alpha Flex</strong>: Edit Mode &gt; Faces &gt; "Enable Alpha" (BLEND mode).
<ul dir="auto">
<li>Dial "Alpha Value" (0-1) on targets.</li>
</ul>
</li>
</ul>
</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>Saves originals in obj props—undo-proof.</li>
<li>Dye-job heaven for capes/gear.</li>
</ul>
<h2 dir="auto">6. Exporter &amp; Importer: In/Out Bound</h2>
<p dir="auto" style="white-space: pre-wrap;"><strong>Why?</strong> Frictionless .dat I/O with drop smarts.</p>
<p dir="auto" style="white-space: pre-wrap;"><strong>Step-by-Step</strong>:</p>
<ul dir="auto">
<li><strong>Export</strong> (<strong>Model Exporter</strong>, Object Mode):
<ul dir="auto">
<li>"Output Directory" set.</li>
<li>Meshes selected.</li>
<li><strong>Picks</strong>:
<ul dir="auto">
<li>"DAT (Weight-Based)": VSKIN-sniff (BODY? HEAD?), spits normal + _drop.dat.</li>
<li>"DAT (Custom Color)": RSPRI/TSKIN/VSKIN feast; drop auto.</li>
</ul>
</li>
<li>Export—<span>ModelName.dat</span> &amp; <span>_drop.dat</span> done.</li>
</ul>
</li>
<li><strong>Import</strong> (File &gt; Import):
<ul dir="auto">
<li>"317/OSRS": Basics (UVs/weights).</li>
<li>"667": Full monty (complex tex/PMN).</li>
<li><span>texture_dump</span> required; layers auto-spawn.</li>
</ul>
</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;"><strong>Pro Moves</strong>:</p>
<ul dir="auto">
<li>Drops twist/translate (SWORD: 90° spin).</li>
<li>Detect: Weights like {1,2,3}=HEAD.</li>
<li>"Make Render RS Style": Cel-shade viewport.</li>
</ul>
<h2 dir="auto">Power User Hacks</h2>
<ul dir="auto">
<li><strong>Perf Boost</strong>: High-poly? Kill overlays.</li>
<li><strong>Keymaps</strong>: Stock none—bless 'em in Preferences &gt; Keymap.</li>
<li><strong>Code Tweaks</strong>: .py paradise (e.g., weighter.py presets).</li>
<li><strong>Debug</strong>: Console dive for oopsies. Ping Discord @dimension5879 for fixes.</li>
<li><strong>Changelog</strong>: Importer split in v7.7—peek bl_info.</li>
</ul>
<h2 dir="auto">Shoutouts</h2>
<ul dir="auto">
<li><strong>Creator</strong>: Epic AI Game Dev (Gemini-boosted).</li>
<li><strong>License</strong>: MIT—RSPS-free, share with cred.</li>
<li><strong>Nods</strong>: RS modders for format lore.</li>
</ul>
<p dir="auto" style="white-space: pre-wrap;">Forge on, scaper! Questions? Hit the Discord. 🚀</p><!--EndFragment-->
</body>
</html>
