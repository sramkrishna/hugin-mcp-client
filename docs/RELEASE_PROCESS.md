# Odinson Release Process

## Pre-Release Checklist

- [ ] All critical bugs fixed
- [ ] Code review completed
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in `pyproject.toml`
- [ ] Demo/examples tested
- [ ] Security audit completed

## Release Steps

1. **Create Release Branch**
   ```bash
   git checkout -b release/v1.0.0
   ```

2. **Final Testing**
   - Test all MCP servers (Ratatoskr, Muninn, Yggdrasil)
   - Test with Claude API
   - Test with Ollama (local)
   - Verify calendar, email, GitLab integrations

3. **Update Version**
   ```bash
   # Edit pyproject.toml
   version = "1.0.0"
   ```

4. **Create Git Tag**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0 - Odinson Personal AI System"
   git push origin v1.0.0
   ```

5. **Build and Publish** (if publishing to PyPI)
   ```bash
   python -m build
   twine upload dist/*
   ```

6. **Create GitHub Release**
   - Go to GitHub Releases
   - Create new release from tag
   - Add release notes from CHANGELOG
   - Attach any binaries/installers

## Post-Release Checklist

- [ ] **Create `develop` branch for ongoing work**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b develop
   git push -u origin develop
   ```

- [ ] **Set `develop` as default branch on GitHub** (for PRs)
- [ ] Update README with installation instructions
- [ ] Announce release (blog post, social media, mailing list)
- [ ] Create milestone for next release (v1.1.0)
- [ ] Move unfinished items to next milestone
- [ ] Document any known issues in GitHub Issues

## Development Branch Workflow (Post v1.0)

### Branch Structure:
```
main          # Stable releases only (v1.0.0, v1.1.0, etc.)
  └─ develop  # Integration branch for features
      ├─ feature/link-events
      ├─ feature/github-integration
      └─ bugfix/gitlab-env-var
```

### Workflow:
1. **New features**: Branch from `develop`, PR back to `develop`
2. **Bug fixes**: Branch from `develop`, PR back to `develop`
3. **Hotfixes**: Branch from `main`, PR to both `main` and `develop`
4. **Releases**: Merge `develop` → `main` when ready

### Example:
```bash
# Start new feature
git checkout develop
git pull origin develop
git checkout -b feature/my-feature

# ... work on feature ...

# Create PR
git push origin feature/my-feature
# Open PR: feature/my-feature → develop

# After merge, delete feature branch
git branch -d feature/my-feature
```

## Version Numbering (Semantic Versioning)

- **Major (1.0.0)**: Breaking changes, major new features
- **Minor (1.1.0)**: New features, backwards compatible
- **Patch (1.0.1)**: Bug fixes only

## Release Notes Template

```markdown
# Odinson v1.0.0 - "The First Flight"

Release Date: YYYY-MM-DD

## What's New

### Features
- 🦅 Hugin orchestration with multi-provider LLM support
- 🧠 Muninn RAG for semantic memory
- 📬 Ratatoskr GNOME desktop integration
- 🌳 Yggdrasil GitLab/GitHub connectivity

### Bug Fixes
- Fixed calendar timezone handling
- Fixed input line wrapping
- Added current datetime to system context

### Breaking Changes
- None (initial release)

## Installation

\`\`\`bash
pip install hugin-mcp-client
\`\`\`

## Documentation
- [Getting Started](docs/GETTING_STARTED.md)
- [Demo Script](DEMO_SCRIPT.md)
- [Architecture](docs/MULTI_AGENT_ARCHITECTURE.md)
```

## Hotfix Process (Emergency Fixes)

If critical bug found in `main`:

```bash
# Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug

# Fix the bug
# ... commit changes ...

# Create PRs to BOTH main and develop
git push origin hotfix/critical-bug
# PR #1: hotfix/critical-bug → main (tag as v1.0.1)
# PR #2: hotfix/critical-bug → develop

# After merges, delete hotfix branch
```

## Notes

- Keep `main` clean - only merge tested, release-ready code
- Use `develop` for integration and testing
- Feature branches should be short-lived (< 1 week)
- Always test before merging to `develop`
- Always code review before merging to `main`
