/** Regras do dependency-cruiser. Ajuste `path` às pastas do projeto. */
module.exports = {
  forbidden: [
    { name: "no-circular", severity: "error", from: {}, to: { circular: true } },
    { name: "ui-nao-importa-dominio-ao-contrario", severity: "error", from: { path: "^src/dominio" }, to: { path: "^src/ui" } },
  ],
  options: { tsConfig: { fileName: "tsconfig.json" }, doNotFollow: { path: "node_modules" } },
};
