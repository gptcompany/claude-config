/**
 * MCP Client - Memory and Pattern Storage for Claude Code Hooks
 *
 * Ported from /media/sam/1TB/claude-hooks-shared/hooks/core/mcp_client.py
 *
 * Provides:
 * - Memory store/retrieve (JSON file storage)
 * - Pattern storage for learning
 * - Project and timestamp utilities
 *
 * Storage location: ~/.claude-flow/memory/store.json
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// Configuration
const HOME_DIR = os.homedir();
const MCP_STORE_DIR = path.join(HOME_DIR, '.claude-flow', 'memory');
const MCP_STORE_FILE = path.join(MCP_STORE_DIR, 'store.json');
const PATTERNS_FILE = path.join(MCP_STORE_DIR, 'patterns.json');

/**
 * Ensure the MCP store directory and file exist
 */
function ensureStore() {
  try {
    if (!fs.existsSync(MCP_STORE_DIR)) {
      fs.mkdirSync(MCP_STORE_DIR, { recursive: true });
    }
    if (!fs.existsSync(MCP_STORE_FILE)) {
      fs.writeFileSync(MCP_STORE_FILE, JSON.stringify({ entries: {} }, null, 2));
    }
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Load the MCP store from disk
 * @returns {object} The store object with 'entries' key
 */
function loadStore() {
  ensureStore();
  try {
    const data = fs.readFileSync(MCP_STORE_FILE, 'utf8');
    const parsed = JSON.parse(data);
    if (!parsed.entries) {
      parsed.entries = {};
    }
    return parsed;
  } catch (err) {
    return { entries: {} };
  }
}

/**
 * Save the MCP store to disk
 * @param {object} store - The store object to save
 * @returns {boolean} Success status
 */
function saveStore(store) {
  ensureStore();
  try {
    fs.writeFileSync(MCP_STORE_FILE, JSON.stringify(store, null, 2));
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Get current project name from environment or git repo
 * @returns {string} Project name
 */
function getProjectName() {
  // Check environment variable first
  if (process.env.CLAUDE_PROJECT) {
    return process.env.CLAUDE_PROJECT;
  }

  // Try to get from git
  try {
    const result = execSync('git rev-parse --show-toplevel', {
      encoding: 'utf8',
      timeout: 5000,
      stdio: ['pipe', 'pipe', 'pipe']
    });
    return path.basename(result.trim());
  } catch (err) {
    // Fall back to current directory name
    return path.basename(process.cwd());
  }
}

/**
 * Get ISO timestamp
 * @returns {string} ISO formatted timestamp
 */
function getTimestamp() {
  return new Date().toISOString();
}

/**
 * Store a value in MCP memory
 * @param {string} key - The key to store under
 * @param {any} value - The value to store (will be JSON serialized)
 * @param {string} [namespace=''] - Optional namespace prefix
 * @returns {object} Result object with success flag
 */
function memoryStore(key, value, namespace = '') {
  try {
    const fullKey = namespace ? `${namespace}:${key}` : key;
    const store = loadStore();
    const now = getTimestamp();

    store.entries[fullKey] = {
      key: fullKey,
      value: value,
      metadata: {},
      storedAt: now,
      accessCount: 0,
      lastAccessed: now
    };

    const success = saveStore(store);
    return { success, direct: true };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

/**
 * Retrieve a value from MCP memory
 * @param {string} key - The key to retrieve
 * @param {string} [namespace=''] - Optional namespace prefix
 * @returns {any} The stored value or null if not found
 */
function memoryRetrieve(key, namespace = '') {
  try {
    const fullKey = namespace ? `${namespace}:${key}` : key;
    const store = loadStore();

    if (store.entries[fullKey]) {
      const entry = store.entries[fullKey];
      // Update access count and timestamp
      entry.accessCount = (entry.accessCount || 0) + 1;
      entry.lastAccessed = getTimestamp();
      saveStore(store);

      const value = entry.value;
      // Try to parse JSON string values
      if (typeof value === 'string') {
        try {
          return JSON.parse(value);
        } catch {
          return value;
        }
      }
      return value;
    }
    return null;
  } catch (err) {
    return null;
  }
}

/**
 * List all memory keys
 * @param {string} [namespace=''] - Optional namespace to filter by
 * @returns {string[]} Array of keys
 */
function memoryList(namespace = '') {
  try {
    const store = loadStore();
    const keys = Object.keys(store.entries);
    if (namespace) {
      return keys.filter(k => k.startsWith(`${namespace}:`));
    }
    return keys;
  } catch (err) {
    return [];
  }
}

/**
 * Delete a value from MCP memory
 * @param {string} key - The key to delete
 * @param {string} [namespace=''] - Optional namespace prefix
 * @returns {boolean} Success status
 */
function memoryDelete(key, namespace = '') {
  try {
    const fullKey = namespace ? `${namespace}:${key}` : key;
    const store = loadStore();
    if (store.entries[fullKey]) {
      delete store.entries[fullKey];
      return saveStore(store);
    }
    return false;
  } catch (err) {
    return false;
  }
}

/**
 * Search memory by prefix
 * @param {string} prefix - Key prefix to search for
 * @returns {object[]} Array of matching entries
 */
function memorySearch(prefix) {
  try {
    const store = loadStore();
    const results = [];
    for (const [key, entry] of Object.entries(store.entries)) {
      if (key.startsWith(prefix)) {
        results.push({ key, value: entry.value, storedAt: entry.storedAt });
      }
    }
    return results;
  } catch (err) {
    return [];
  }
}

/**
 * Load patterns from disk
 * @returns {object} Patterns object with 'patterns' array
 */
function loadPatterns() {
  ensureStore();
  try {
    if (!fs.existsSync(PATTERNS_FILE)) {
      fs.writeFileSync(PATTERNS_FILE, JSON.stringify({ patterns: [] }, null, 2));
    }
    const data = fs.readFileSync(PATTERNS_FILE, 'utf8');
    const parsed = JSON.parse(data);
    if (!parsed.patterns) {
      parsed.patterns = [];
    }
    return parsed;
  } catch (err) {
    return { patterns: [] };
  }
}

/**
 * Save patterns to disk
 * @param {object} patternsData - The patterns object to save
 * @returns {boolean} Success status
 */
function savePatterns(patternsData) {
  ensureStore();
  try {
    fs.writeFileSync(PATTERNS_FILE, JSON.stringify(patternsData, null, 2));
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Store a learned pattern
 * @param {string} pattern - Pattern description
 * @param {string} type - Pattern type (e.g., 'error', 'success', 'workflow')
 * @param {number} confidence - Confidence score (0-1)
 * @param {object} [metadata={}] - Additional metadata
 * @returns {object} Result object with success flag
 */
function patternStore(pattern, type, confidence, metadata = {}) {
  try {
    const patternsData = loadPatterns();
    const now = getTimestamp();
    const project = getProjectName();

    const newPattern = {
      id: `pattern_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      pattern,
      type,
      confidence: Math.min(1, Math.max(0, confidence)),
      metadata,
      project,
      createdAt: now,
      usageCount: 0
    };

    patternsData.patterns.push(newPattern);

    // Keep only the last 1000 patterns
    if (patternsData.patterns.length > 1000) {
      patternsData.patterns = patternsData.patterns.slice(-1000);
    }

    const success = savePatterns(patternsData);
    return { success, patternId: newPattern.id };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

/**
 * Search patterns by type or content
 * @param {string} query - Search query
 * @param {string} [type=''] - Optional type filter
 * @param {number} [minConfidence=0] - Minimum confidence threshold
 * @param {number} [limit=10] - Maximum results
 * @returns {object[]} Array of matching patterns
 */
function patternSearch(query, type = '', minConfidence = 0, limit = 10) {
  try {
    const patternsData = loadPatterns();
    let results = patternsData.patterns;

    // Filter by type
    if (type) {
      results = results.filter(p => p.type === type);
    }

    // Filter by confidence
    results = results.filter(p => p.confidence >= minConfidence);

    // Filter by query (case-insensitive)
    if (query) {
      const lowerQuery = query.toLowerCase();
      results = results.filter(p =>
        p.pattern.toLowerCase().includes(lowerQuery) ||
        (p.metadata && JSON.stringify(p.metadata).toLowerCase().includes(lowerQuery))
      );
    }

    // Sort by confidence descending, then by creation date
    results.sort((a, b) => {
      if (b.confidence !== a.confidence) {
        return b.confidence - a.confidence;
      }
      return new Date(b.createdAt) - new Date(a.createdAt);
    });

    return results.slice(0, limit);
  } catch (err) {
    return [];
  }
}

/**
 * Get patterns for the current project
 * @param {number} [limit=20] - Maximum results
 * @returns {object[]} Array of patterns for this project
 */
function getProjectPatterns(limit = 20) {
  try {
    const project = getProjectName();
    const patternsData = loadPatterns();
    return patternsData.patterns
      .filter(p => p.project === project)
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
      .slice(0, limit);
  } catch (err) {
    return [];
  }
}

module.exports = {
  // Core memory operations
  memoryStore,
  memoryRetrieve,
  memoryList,
  memoryDelete,
  memorySearch,

  // Pattern operations
  patternStore,
  patternSearch,
  getProjectPatterns,

  // Utilities
  getProjectName,
  getTimestamp,

  // Constants (for testing)
  MCP_STORE_DIR,
  MCP_STORE_FILE,
  PATTERNS_FILE
};
