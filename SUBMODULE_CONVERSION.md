# Converting to Proper Git Submodules

## Status Summary

### ✅ Completed

1. **Ratatoskr** - Committed and pushed to GitHub
   - Fixed pyproject.toml syntax errors
   - Fixed email reading (Maildir format)
   - Fixed calendar timezone bugs
   - Fixed video URL handling
   - Added justfile
   - Commit: 4adc865
   - URL: https://github.com/sramkrishna/ratatoskr-mcp-server

2. **Muninn** - Committed and pushed to GitHub
   - Added justfile
   - Commit: 0bd1d8d
   - URL: https://github.com/sramkrishna/muninn-mcp-server

3. **Hugin** - Committed and pushed to GitHub
   - Added OpenVINO support
   - Added justfile
   - Added SETUP.md documentation
   - Commit: 2fc88a9
   - URL: https://github.com/sramkrishna/hugin-mcp-client

### ⏳ Pending

4. **Yggdrasil** - Local repo initialized, needs GitHub push
   - Local commit: fb4e82d
   - Needs GitHub repository creation
   - Then push to GitHub

## Next Steps

### Step 1: Push Yggdrasil to GitHub

See `/var/home/sri/Projects/yggdrasil-mcp-server/PUSH_TO_GITHUB.md` for detailed instructions.

**Quick version:**

```bash
# Create repo on GitHub: https://github.com/new
# Name: yggdrasil-mcp-server
# Then:
cd /var/home/sri/Projects/yggdrasil-mcp-server
git remote add origin https://github.com/sramkrishna/yggdrasil-mcp-server.git
git push -u origin main
```

### Step 2: Convert Hugin to Use Proper Submodules

Once Yggdrasil is on GitHub:

```bash
cd /var/home/sri/Projects/hugin-mcp-client

# Backup current servers/ (optional)
cp -r servers servers.backup

# Remove copied directories
rm -rf servers/ratatoskr servers/muninn servers/yggdrasil

# Add proper git submodules pointing to GitHub
git submodule add https://github.com/sramkrishna/ratatoskr-mcp-server.git servers/ratatoskr
git submodule add https://github.com/sramkrishna/muninn-mcp-server.git servers/muninn
git submodule add https://github.com/sramkrishna/yggdrasil-mcp-server.git servers/yggdrasil

# Initialize and update submodules to latest commits
git submodule update --init --recursive

# Verify all justfiles are present
ls servers/*/justfile

# Test setup
just setup-all
```

### Step 3: Commit Submodule Configuration

```bash
# Stage submodule configuration
git add .gitmodules servers/

# Commit
git commit -m "$(cat <<'EOF'
Convert servers to proper git submodules

- Ratatoskr: https://github.com/sramkrishna/ratatoskr-mcp-server (4adc865)
- Muninn: https://github.com/sramkrishna/muninn-mcp-server (0bd1d8d)
- Yggdrasil: https://github.com/sramkrishna/yggdrasil-mcp-server (fb4e82d)

All servers now have:
- justfile for standardized setup
- Proper dependency declarations
- Consistent structure

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# Push
git push
```

### Step 4: Test Fresh Clone

Test that everything works from a fresh clone:

```bash
# Clone to a temp location
cd /tmp
git clone --recurse-submodules https://github.com/sramkrishna/hugin-mcp-client.git
cd hugin-mcp-client

# Setup everything
just setup-all

# Run Hugin
just run
```

## How Submodules Work

Once converted:

### Updating Submodules

```bash
# Update all submodules to latest commits
just update-submodules

# Or manually:
git submodule update --remote
```

### Working on a Submodule

```bash
# Go into submodule
cd servers/ratatoskr

# Make changes
git checkout -b my-feature
# ... edit files ...
git commit -m "My changes"
git push origin my-feature

# Go back to Hugin
cd ../..

# Update Hugin to use new submodule commit
git add servers/ratatoskr
git commit -m "Update Ratatoskr submodule"
git push
```

### Cloning with Submodules

```bash
# Option 1: Clone with submodules
git clone --recurse-submodules https://github.com/sramkrishna/hugin-mcp-client.git

# Option 2: Clone first, then get submodules
git clone https://github.com/sramkrishna/hugin-mcp-server.git
cd hugin-mcp-client
git submodule update --init --recursive
```

## Current Working State

Your current `/var/home/sri/Projects/hugin-mcp-client/servers/` contains:
- **Copied** versions of the MCP servers
- These work fine for local development
- BUT they're not tracked as proper git submodules yet

After conversion:
- `servers/` will contain **git submodule references**
- Each server directory will point to a specific commit in its own repo
- Changes to servers require commit+push in the submodule, then update in Hugin

## Benefits of Proper Submodules

1. **Independent Development**: Each server has its own git history
2. **Version Pinning**: Hugin pins specific commits of each server
3. **Easy Updates**: `git submodule update --remote` pulls latest versions
4. **Clean Separation**: Each repo can be cloned/tested independently
5. **GitHub Actions**: Each repo can have its own CI/CD

## Tonight's Demo

You can use the current setup (copied servers) for tonight's demo - everything works!

The submodule conversion can be done afterward as a cleanup task.

## Verification Checklist

After conversion, verify:

- [ ] `git submodule status` shows all three servers
- [ ] `just setup-all` works
- [ ] `just run` starts Hugin with all MCP servers
- [ ] Fresh clone works: `git clone --recurse-submodules`
- [ ] Submodule update works: `just update-submodules`
