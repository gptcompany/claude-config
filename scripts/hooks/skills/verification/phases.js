#!/usr/bin/env node
/**
 * Verification Phases Configuration
 *
 * Defines the 6-phase sequential verification pipeline:
 * 1. Build - Compile/transpile code
 * 2. Type Check - Static type analysis
 * 3. Lint - Code quality checks
 * 4. Tests - Run test suites
 * 5. Security - Vulnerability scanning
 * 6. Diff - Show pending changes
 *
 * Each phase supports multiple project types (npm, python, go, rust, etc.)
 *
 * Part of: Skills Port (Phase 15)
 * Source: ECC verification-loop skill
 */

const fs = require("fs");
const path = require("path");

/**
 * Verification phases configuration
 *
 * @property {string} name - Phase identifier
 * @property {string} displayName - Human-readable name
 * @property {Object} commands - Project type to command mapping
 * @property {boolean} failFast - Stop verification if this phase fails
 * @property {number} timeout - Maximum execution time in ms
 * @property {number} outputLimit - Max lines to show from output
 */
const PHASES = [
  {
    name: "build",
    displayName: "Build",
    commands: {
      npm: "npm run build 2>&1",
      yarn: "yarn build 2>&1",
      pnpm: "pnpm build 2>&1",
      make: "make build 2>&1",
      cargo: "cargo build 2>&1",
      go: "go build ./... 2>&1",
      python:
        'python -m py_compile $(find . -name "*.py" -not -path "./venv/*" -not -path "./.venv/*" 2>/dev/null | head -50) 2>&1',
      gradle: "./gradlew build 2>&1",
      maven: "mvn compile 2>&1",
    },
    failFast: true,
    timeout: 120000,
    outputLimit: 50,
  },
  {
    name: "typecheck",
    displayName: "Type Check",
    commands: {
      typescript: "npx tsc --noEmit 2>&1",
      mypy: "mypy . 2>&1",
      pyright: "pyright 2>&1",
      flow: "npx flow check 2>&1",
    },
    failFast: true,
    timeout: 60000,
    outputLimit: 30,
  },
  {
    name: "lint",
    displayName: "Lint",
    commands: {
      eslint: "npm run lint 2>&1 | head -30",
      ruff: "ruff check . 2>&1 | head -30",
      golangci: "golangci-lint run 2>&1 | head -30",
      clippy: "cargo clippy 2>&1 | head -30",
      rubocop: "rubocop 2>&1 | head -30",
      shellcheck: "shellcheck *.sh 2>&1 | head -30",
    },
    failFast: false,
    timeout: 60000,
    outputLimit: 30,
  },
  {
    name: "test",
    displayName: "Tests",
    commands: {
      npm: "npm test 2>&1 | tail -50",
      jest: "npx jest --passWithNoTests 2>&1 | tail -50",
      vitest: "npx vitest run 2>&1 | tail -50",
      pytest: "pytest -v 2>&1 | tail -50",
      go: "go test ./... 2>&1 | tail -50",
      cargo: "cargo test 2>&1 | tail -50",
      mocha: "npx mocha 2>&1 | tail -50",
      node: "node --test 2>&1 | tail -50",
      rspec: "rspec 2>&1 | tail -50",
    },
    failFast: true,
    timeout: 180000,
    outputLimit: 50,
  },
  {
    name: "security",
    displayName: "Security",
    commands: {
      npm: "npm audit --audit-level=high 2>&1 | head -20",
      snyk: "snyk test 2>&1 | head -20",
      trivy: "trivy fs . 2>&1 | head -20",
      bandit: "bandit -r . 2>&1 | head -20",
      safety: "safety check 2>&1 | head -20",
      cargo: "cargo audit 2>&1 | head -20",
    },
    failFast: false,
    timeout: 60000,
    outputLimit: 20,
  },
  {
    name: "diff",
    displayName: "Changes",
    commands: {
      git: "git diff --stat 2>&1 && git diff --cached --stat 2>&1",
    },
    failFast: false,
    timeout: 10000,
    outputLimit: 30,
  },
];

/**
 * Project type detection based on files in the current directory
 *
 * @param {string} cwd - Working directory to check (defaults to process.cwd())
 * @returns {Object} Detected project info { type, variant, confidence }
 */
function detectProjectType(cwd = process.cwd()) {
  const exists = (filename) => {
    try {
      return fs.existsSync(path.join(cwd, filename));
    } catch {
      return false;
    }
  };

  // Check for package.json (JavaScript/TypeScript)
  if (exists("package.json")) {
    try {
      const pkg = JSON.parse(
        fs.readFileSync(path.join(cwd, "package.json"), "utf8"),
      );
      const hasTypescript =
        exists("tsconfig.json") ||
        (pkg.devDependencies && pkg.devDependencies.typescript) ||
        (pkg.dependencies && pkg.dependencies.typescript);

      // Detect test framework
      const hasJest =
        (pkg.devDependencies && pkg.devDependencies.jest) ||
        (pkg.dependencies && pkg.dependencies.jest) ||
        exists("jest.config.js") ||
        exists("jest.config.ts");

      const hasVitest =
        (pkg.devDependencies && pkg.devDependencies.vitest) ||
        (pkg.dependencies && pkg.dependencies.vitest) ||
        exists("vitest.config.js") ||
        exists("vitest.config.ts");

      const hasMocha =
        (pkg.devDependencies && pkg.devDependencies.mocha) ||
        (pkg.dependencies && pkg.dependencies.mocha);

      // Detect package manager
      let manager = "npm";
      if (exists("pnpm-lock.yaml")) manager = "pnpm";
      else if (exists("yarn.lock")) manager = "yarn";

      return {
        type: "node",
        typescript: hasTypescript,
        testFramework: hasJest
          ? "jest"
          : hasVitest
            ? "vitest"
            : hasMocha
              ? "mocha"
              : "node",
        packageManager: manager,
        confidence: 0.95,
      };
    } catch {
      return { type: "node", confidence: 0.7 };
    }
  }

  // Python projects
  if (
    exists("pyproject.toml") ||
    exists("setup.py") ||
    exists("requirements.txt")
  ) {
    const hasMypy = exists("mypy.ini") || exists(".mypy.ini");
    const hasPyright = exists("pyrightconfig.json");
    const hasRuff = exists("ruff.toml") || exists(".ruff.toml");

    return {
      type: "python",
      typeChecker: hasMypy ? "mypy" : hasPyright ? "pyright" : null,
      linter: hasRuff ? "ruff" : "default",
      confidence: 0.9,
    };
  }

  // Go projects
  if (exists("go.mod")) {
    return {
      type: "go",
      confidence: 0.95,
    };
  }

  // Rust projects
  if (exists("Cargo.toml")) {
    return {
      type: "rust",
      confidence: 0.95,
    };
  }

  // Makefile-based projects
  if (exists("Makefile")) {
    return {
      type: "make",
      confidence: 0.6,
    };
  }

  // Java projects
  if (exists("build.gradle") || exists("build.gradle.kts")) {
    return {
      type: "gradle",
      confidence: 0.9,
    };
  }

  if (exists("pom.xml")) {
    return {
      type: "maven",
      confidence: 0.9,
    };
  }

  // Ruby projects
  if (exists("Gemfile")) {
    return {
      type: "ruby",
      confidence: 0.9,
    };
  }

  // Check for git at minimum
  if (exists(".git")) {
    return {
      type: "generic",
      confidence: 0.3,
    };
  }

  return {
    type: "unknown",
    confidence: 0,
  };
}

/**
 * Get the appropriate command for a phase based on project type
 *
 * @param {Object} phase - Phase configuration object
 * @param {Object} projectInfo - Project type info from detectProjectType()
 * @returns {string|null} Command to run, or null if not applicable
 */
function getPhaseCommand(phase, projectInfo) {
  const {
    type,
    typescript,
    testFramework,
    packageManager,
    typeChecker,
    linter,
  } = projectInfo;

  switch (phase.name) {
    case "build":
      if (type === "node") {
        return phase.commands[packageManager] || phase.commands.npm;
      }
      if (type === "rust") return phase.commands.cargo;
      if (type === "go") return phase.commands.go;
      if (type === "python") return phase.commands.python;
      if (type === "make") return phase.commands.make;
      if (type === "gradle") return phase.commands.gradle;
      if (type === "maven") return phase.commands.maven;
      return null;

    case "typecheck":
      if (type === "node" && typescript) {
        return phase.commands.typescript;
      }
      if (type === "python") {
        if (typeChecker === "mypy") return phase.commands.mypy;
        if (typeChecker === "pyright") return phase.commands.pyright;
        return null;
      }
      return null;

    case "lint":
      if (type === "node") return phase.commands.eslint;
      if (type === "python") return phase.commands.ruff;
      if (type === "go") return phase.commands.golangci;
      if (type === "rust") return phase.commands.clippy;
      if (type === "ruby") return phase.commands.rubocop;
      return null;

    case "test":
      if (type === "node") {
        if (testFramework === "jest") return phase.commands.jest;
        if (testFramework === "vitest") return phase.commands.vitest;
        if (testFramework === "mocha") return phase.commands.mocha;
        if (testFramework === "node") return phase.commands.node;
        return phase.commands.npm;
      }
      if (type === "python") return phase.commands.pytest;
      if (type === "go") return phase.commands.go;
      if (type === "rust") return phase.commands.cargo;
      if (type === "ruby") return phase.commands.rspec;
      return null;

    case "security":
      if (type === "node") return phase.commands.npm;
      if (type === "python")
        return phase.commands.bandit || phase.commands.safety;
      if (type === "rust") return phase.commands.cargo;
      return null;

    case "diff":
      return phase.commands.git;

    default:
      return null;
  }
}

/**
 * Get phases that apply to a project type
 *
 * @param {Object} projectInfo - Project type info from detectProjectType()
 * @returns {Array} Applicable phases with commands
 */
function getApplicablePhases(projectInfo) {
  return PHASES.map((phase) => {
    const command = getPhaseCommand(phase, projectInfo);
    return {
      ...phase,
      command,
      applicable: command !== null,
    };
  });
}

module.exports = {
  PHASES,
  detectProjectType,
  getPhaseCommand,
  getApplicablePhases,
};
