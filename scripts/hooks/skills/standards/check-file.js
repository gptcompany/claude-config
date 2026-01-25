#!/usr/bin/env node
/**
 * Check File Script - Manual coding standards checker
 *
 * Usage: node check-file.js <file-or-directory>
 *
 * Checks files against coding standards patterns and reports issues.
 */

const fs = require("fs");
const path = require("path");
const { checkPatterns, detectFileType } = require("./patterns");

// ANSI colors
const colors = {
  reset: "\x1b[0m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  gray: "\x1b[90m",
  bold: "\x1b[1m",
};

/**
 * Get all files in directory recursively
 * @param {string} dir - Directory path
 * @param {string[]} files - Accumulated files
 * @returns {string[]} - All file paths
 */
function getFilesRecursively(dir, files = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    // Skip common ignore directories
    if (
      entry.isDirectory() &&
      [
        "node_modules",
        ".git",
        "dist",
        "build",
        "vendor",
        "venv",
        ".venv",
        "__pycache__",
        ".next",
        "coverage",
      ].includes(entry.name)
    ) {
      continue;
    }

    if (entry.isDirectory()) {
      getFilesRecursively(fullPath, files);
    } else if (detectFileType(fullPath)) {
      files.push(fullPath);
    }
  }

  return files;
}

/**
 * Check a single file
 * @param {string} filePath - Path to file
 * @returns {Object} - { file, issues, passed }
 */
function checkFile(filePath) {
  try {
    const content = fs.readFileSync(filePath, "utf8");
    const { passed, issues } = checkPatterns(content, filePath);
    return { file: filePath, issues, passed };
  } catch (err) {
    return { file: filePath, issues: [], passed: true, error: err.message };
  }
}

/**
 * Format issue for display
 * @param {Object} issue - Issue object
 * @returns {string} - Formatted issue
 */
function formatIssue(issue) {
  const severityColors = {
    error: colors.red,
    warn: colors.yellow,
    info: colors.blue,
  };

  const severitySymbols = {
    error: "ERROR",
    warn: "WARN ",
    info: "INFO ",
  };

  const color = severityColors[issue.severity] || colors.gray;
  const symbol = severitySymbols[issue.severity] || "     ";

  return `  ${color}${symbol}${colors.reset} L${issue.line}: ${issue.message}\n         ${colors.gray}${issue.content}${colors.reset}`;
}

/**
 * Main function
 */
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.log("Usage: node check-file.js <file-or-directory>");
    console.log("\nExamples:");
    console.log("  node check-file.js src/index.js");
    console.log("  node check-file.js src/");
    process.exit(1);
  }

  const targetPath = args[0];

  // Resolve path
  const resolvedPath = path.resolve(targetPath);

  if (!fs.existsSync(resolvedPath)) {
    console.error(`Error: Path not found: ${resolvedPath}`);
    process.exit(1);
  }

  // Get files to check
  let files = [];
  const stat = fs.statSync(resolvedPath);

  if (stat.isDirectory()) {
    files = getFilesRecursively(resolvedPath);
  } else {
    files = [resolvedPath];
  }

  if (files.length === 0) {
    console.log("No supported files found to check.");
    process.exit(0);
  }

  console.log(
    `\n${colors.bold}Checking ${files.length} file(s)...${colors.reset}\n`,
  );

  // Check all files
  let totalIssues = 0;
  let errorCount = 0;
  let warnCount = 0;
  let infoCount = 0;
  let filesWithIssues = 0;

  for (const file of files) {
    const result = checkFile(file);

    if (result.error) {
      console.log(
        `${colors.gray}Skipped: ${file} (${result.error})${colors.reset}`,
      );
      continue;
    }

    if (result.issues.length > 0) {
      filesWithIssues++;
      const relativePath = path.relative(process.cwd(), result.file);
      console.log(`${colors.bold}${relativePath}${colors.reset}`);

      for (const issue of result.issues) {
        console.log(formatIssue(issue));
        totalIssues++;

        if (issue.severity === "error") errorCount++;
        else if (issue.severity === "warn") warnCount++;
        else infoCount++;
      }

      console.log("");
    }
  }

  // Summary
  console.log(`${colors.bold}Summary${colors.reset}`);
  console.log(`  Files checked: ${files.length}`);
  console.log(`  Files with issues: ${filesWithIssues}`);
  console.log(`  Total issues: ${totalIssues}`);

  if (totalIssues > 0) {
    console.log("");
    if (errorCount > 0)
      console.log(`  ${colors.red}Errors: ${errorCount}${colors.reset}`);
    if (warnCount > 0)
      console.log(`  ${colors.yellow}Warnings: ${warnCount}${colors.reset}`);
    if (infoCount > 0)
      console.log(`  ${colors.blue}Info: ${infoCount}${colors.reset}`);
  }

  // Exit code based on errors
  process.exit(errorCount > 0 ? 1 : 0);
}

main();
