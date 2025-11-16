# Claude Code Context

## Important Development Requirements

### Environment
**CRITICAL: Always run Claude Code from INSIDE the toolbox, NOT on the host**

When running Claude Code on this system:
- The host uses Bluefin/Silverblue (immutable OS) with linuxbrew
- Linuxbrew only exists on the HOST, NOT in the toolbox container
- Development work should happen in the toolbox where system packages are mutable
- To enter toolbox: `toolbox enter`
- Check if in toolbox: `cat /etc/os-release | grep -i toolbox` (should show "Toolbx Container Image")

### Python Version
**IMPORTANT: Use Python 3.13 ONLY**

- All setup scripts, justfile recipes, and venvs MUST use `python3.13`
- Do NOT use `python3` or `python3.14`
- **DO NOT use linuxbrew's python3.13** - Use system python3.13 only
- Python 3.14 is not yet supported by some dependencies (particularly numpy < 2.0 required by chromadb)
- This applies to:
  - Hugin main client
  - Ratatoskr MCP server
  - Muninn MCP server
  - Yggdrasil MCP server

**Linuxbrew vs Toolbox:**
- **Linuxbrew only exists on the HOST, NOT in toolbox/containers**
- **NEVER use or reference linuxbrew paths** (e.g., `/home/linuxbrew/.linuxbrew/bin/python3.13`)
- All Python symlinks and venvs must point to system Python (`/usr/bin/python3.13`), not linuxbrew
- If venvs break with "bad interpreter: No such file or directory", it's because they were created on the host using linuxbrew
- **Always create venvs from within the toolbox** to ensure they use system Python
- Install python3.13 in toolbox: `sudo dnf install python3.13 python3.13-devel`

**When Python 3.14 gains full support:**
- Update this note
- Update pyproject.toml `requires-python` if needed
- Update justfile `python` variable
- Test all MCP servers with new version

### Required System Dependencies

**OCR Support (for Ratatoskr PDF extraction):**
```bash
sudo dnf install -y poppler-utils tesseract  # Fedora/RHEL
# or
sudo apt install -y poppler-utils tesseract-ocr  # Debian/Ubuntu
```

Required for:
- Extracting text from scanned/image-based PDFs
- `pdfinfo` from poppler-utils (converts PDF to images)
- `tesseract` for OCR text extraction

Without these, PDF OCR will fail with:
- `PDFInfoNotInstalledError: Unable to get page count. Is poppler installed and in PATH?`
- `NotADirectoryError: [Errno 20] Not a directory: 'pdfinfo'`

### Cross-Platform Compatibility
- No toolbox-specific commands in setup scripts
- No distribution-specific assumptions (Fedora, Arch, Debian, Ubuntu should all work)
- Use standard Python venv commands that work everywhere

### Desktop Integration - D-Bus First

**IMPORTANT: Always prefer D-Bus over subprocess calls**

When integrating with the desktop environment (GNOME, KDE, etc.):

- **ALWAYS use D-Bus APIs first** - Cleaner, more reliable, better integration
- **Avoid subprocess calls** when D-Bus alternatives exist
- **Subprocess as last resort** - Only use when no D-Bus API is available

**Examples:**
- ✅ **Network detection**: Use `org.freedesktop.NetworkManager` D-Bus API (NOT `nmcli`, `ip`, `iwgetid`)
- ✅ **File manager**: Use `org.freedesktop.FileManager1.ShowItems` (NOT `nautilus --select`)
- ✅ **Notifications**: Use `org.freedesktop.Notifications` (NOT `notify-send`)
- ✅ **Applications**: Use D-Bus activation when available

**Why D-Bus is better:**
- More reliable and robust
- Proper error handling via GLib/Gio
- Works across different desktop environments
- No shell parsing issues
- Native Python bindings via `gi.repository`
- Already available in Ratatoskr (uses GLib/Gio extensively)

**We already have D-Bus infrastructure:**
- `from gi.repository import Gio, GLib` - Already imported in most modules
- NetworkManager integration - D-Bus based
- File manager integration - D-Bus based
- GNOME app launch monitoring - D-Bus based

**Fallback pattern:**
```python
try:
    # Try D-Bus first
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    proxy = Gio.DBusProxy.new_sync(...)
    result = proxy.call_sync(...)
except:
    # Fallback to subprocess only if D-Bus fails
    subprocess.run([...])
```

### Hugin Configuration

**Max Iterations:**
- Default: 50 iterations per task (increased from 10)
- Location: `src/hugin_mcp_client/orchestrator.py` line 254

**LLM Output Token Limit:**
- Default: 8192 tokens (increased from 4096)
- Location: `src/hugin_mcp_client/llm_client.py` line 39
- Applies to: AnthropicProvider (Claude API)

**Best Practices for Complex Outputs:**
- For visualizations/graphs: Create intermediate data representation (JSON/CSV) first
- Then generate visualization scripts that read from the data file
- Avoid monolithic code generation that hits token limits
- Example workflow:
  1. Extract data → save as `data.json`
  2. Create simple visualization script that loads `data.json`
  3. Keeps outputs modular and under token limits

### Medical Record Analysis - Critical Bias Awareness

**IMPORTANT: Gender Bias in Healthcare - Apply Skepticism to Dismissive Diagnoses**

When analyzing Aarti's (or any woman's) medical records:

- **RED FLAG**: Any diagnosis attributing symptoms to "anxiety" or "stress" as primary cause
- **RED FLAG**: Providers who decline further evaluation and attribute to psychological causes
- **Healthcare reality**: Women's symptoms are systematically dismissed, minimized, or attributed to anxiety
- **This patient's context**:
  - Baseline cognitive function: Near-genius level intellect, fluent in 8 languages, school administrator
  - Current state: Operating at ~15% cognitive capacity due to TBI/POTS
  - **Even at 15%, her cognitive function exceeds 80% of the general population**
  - She researched and identified her own care team while severely cognitively impaired

**Examples from Aarti's records of medical gaslighting:**
- **Dr. Daniel Freedman (Neurology, June 24, 2025)**: Attributed symptoms to anxiety
- **Dr. John Crist (Sports Medicine, April 2025)**: Diagnosed anxiety, declined further evaluation
- Both occurred during March-August 2025 healthcare access gap
- **Breakthrough**: Dr. Powers (neuro-optometry, Aug 27, 2025) took symptoms seriously → referred to NeuroSport

**When processing medical records:**
1. Flag any "anxiety" or "stress" diagnoses for critical review
2. Look for objective evidence (imaging, test results, measurements)
3. Note when providers declined appropriate testing/evaluation
4. Document the patient's advocacy efforts to find appropriate care
5. Recognize gaslighting as a systemic healthcare failure, not patient limitation

**Healthcare access gap (March-August 2025):**
- Not "sparse data" - it's a documentation of systemic failure to provide appropriate care
- Patient had to self-advocate while severely disabled to find competent providers
- This narrative is essential context for understanding treatment delays

### File Organization

**IMPORTANT: Personal/Medical Files Location**
- **DO NOT** create personal or medical files in the `~/Projects/hugin-mcp-client/` directory
- All personal files (medical records, timelines, personal data) belong in `~/Documents/`
- Example: Aarti's POTS medical records → `~/Documents/Medical/Aarti-POTS-Records/`
- This keeps the project directory clean and prevents accidentally committing personal data
- Added to `.gitignore`: medical_*, Aarti*, POTS*, etc.

**When Claude Code or Hugin creates files:**
- Project/code files → `~/Projects/hugin-mcp-client/`
- Personal/medical files → `~/Documents/Medical/` (or appropriate subdirectory)
- Test data → `~/Documents/` (not in project)

### GitLab Security Policy

**READ-ONLY MODE ENFORCED:**
- All GitLab operations via Yggdrasil MCP server are **read-only by default**
- Even though the token has write access, write operations are disabled in code
- This prevents accidental modifications to GitLab issues, merge requests, or projects
- Location: `servers/yggdrasil/src/yggdrasil_mcp_server/providers/gitlab.py`
  - `READ_ONLY = True` (class variable)
- Write operations will raise `RuntimeError` if attempted
- Tools disabled: `create_gitlab_issue`, `update_gitlab_issue`
- Allowed operations: list issues, get issue details, list MRs, list/get projects

**To enable writes** (if ever needed):
- Set `READ_ONLY = False` in `gitlab.py`
- Requires explicit code change, cannot be overridden via config
- This is by design for security

---
Last updated: 2025-11-11
