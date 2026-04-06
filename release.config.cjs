/** @type {import('semantic-release').Options} */
const path = require('path');

module.exports = {
  // HTTPS: git ls-remote без SSH-ключа к origin (локальный релиз см. tools/semantic-release/README.md)
  repositoryUrl:
    process.env.SEMANTIC_RELEASE_REPOSITORY_URL ||
    'https://github.com/mindevis/QMDeploy.git',
  branches: ['main'],
  plugins: [
    '@semantic-release/commit-analyzer',
    '@semantic-release/release-notes-generator',
    ['@semantic-release/changelog', {changelogFile: 'CHANGELOG.md'}],
    [
      '@semantic-release/exec',
      {
        prepareCmd:
          'node "' +
          path.join(__dirname, 'scripts', 'bump-qmdeploy.mjs') +
          '" "${nextRelease.version}"',
      },
    ],
    [
      '@semantic-release/git',
      {
        assets: ['CHANGELOG.md', 'VERSION', 'helm/qm-project/Chart.yaml'],
        message: 'chore(release): ${nextRelease.version} [skip ci]',
      },
    ],
  ],
};
