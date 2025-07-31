const fs = require("fs");

const lock = JSON.parse(fs.readFileSync("package-lock.json", "utf8"));
const pkg = {
  name: lock.name || "my-project",
  version: "1.0.0",
  description: "",
  main: "index.js",
  scripts: {},
  dependencies: {},
  devDependencies: {},
};

const topLevelDeps = lock.packages[""].dependencies || {};
const topLevelDevDeps = lock.packages[""].devDependencies || {};

for (const [dep, ver] of Object.entries(topLevelDeps)) {
  const info = lock.dependencies?.[dep];
  if (info?.version) pkg.dependencies[dep] = `^${info.version}`;
}

for (const [dep, ver] of Object.entries(topLevelDevDeps)) {
  const info = lock.dependencies?.[dep];
  if (info?.version) pkg.devDependencies[dep] = `^${info.version}`;
}

fs.writeFileSync("package.json", JSON.stringify(pkg, null, 2));
console.log("✅ Rebuilt package.json from package-lock.json");

