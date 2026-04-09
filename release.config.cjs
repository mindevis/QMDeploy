/** @type {import('semantic-release').Options} */
const path = require('path');

const pushAndGithub = [
  ['@semantic-release/exec', { publishCmd: 'git push origin main --follow-tags' }],
  [
    '@semantic-release/github',
    {
      successCommentCondition: false,
      failCommentCondition: false,
      releasedLabels: false,
    },
  ],
];

module.exports = {
  // SSH (как у origin); переопределение: SEMANTIC_RELEASE_REPOSITORY_URL
  repositoryUrl:
    process.env.SEMANTIC_RELEASE_REPOSITORY_URL ||
    'git@github.com:mindevis/QMDeploy.git',
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
    ...pushAndGithub,
  ],
};
