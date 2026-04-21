const extensionMap: Record<string, string> = {
  '.ts': 'typescript',
  '.tsx': 'tsx',
  '.js': 'javascript',
  '.mjs': 'javascript',
  '.cjs': 'javascript',
  '.jsx': 'jsx',
  '.py': 'python',
  '.rs': 'rust',
  '.go': 'go',
  '.java': 'java',
  '.kt': 'kotlin',
  '.kts': 'kotlin',
  '.scala': 'scala',
  '.rb': 'ruby',
  '.swift': 'swift',
  '.c': 'c',
  '.h': 'c',
  '.cpp': 'cpp',
  '.cc': 'cpp',
  '.cxx': 'cpp',
  '.hpp': 'cpp',
  '.hxx': 'cpp',
  '.css': 'css',
  '.html': 'markup',
  '.htm': 'markup',
  '.xml': 'markup',
  '.svg': 'markup',
  '.md': 'markdown',
  '.mdx': 'markdown',
  '.json': 'json',
  '.yaml': 'yaml',
  '.yml': 'yaml',
  '.toml': 'toml',
  '.ini': 'ini',
  '.cfg': 'ini',
  '.sql': 'sql',
  '.sh': 'bash',
  '.bash': 'bash',
  '.zsh': 'bash',
  '.graphql': 'graphql',
  '.gql': 'graphql',
  '.hcl': 'hcl',
  '.tf': 'hcl',
};

const filenameMap: Record<string, string> = {
  'Makefile': 'makefile',
  'Dockerfile': 'docker',
  'Justfile': 'makefile',
  'Rakefile': 'ruby',
  'Gemfile': 'ruby',
};

export function detectLanguage(filename: string): string | null {
  const basename = filename.split('/').pop() ?? '';

  if (filenameMap[basename]) {
    return filenameMap[basename];
  }

  const dotIndex = basename.lastIndexOf('.');
  if (dotIndex === -1) return null;

  const ext = basename.slice(dotIndex).toLowerCase();
  return extensionMap[ext] ?? null;
}
