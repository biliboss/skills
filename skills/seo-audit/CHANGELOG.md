# Changelog

Todas as mudanças do skill `seo-audit`. Formato: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/); versões: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-11-06

### Changed

- Learnings from sessions folded in.

## [0.1.0] - 2026-11-06

### Added

- `audit.sh`: os fatos e os achados de SEO de cada página, lidos do HTML sem JavaScript, incluindo o canonical que
  volta por redirecionamento (`canonical-loop`) e o canonical quebrado.
- `sitemap.sh`: os sitemaps do robots.txt, os índices seguidos, o host de cada um e, com `--check`, o status de cada
  URL, com os redirecionamentos agrupados num achado só.
- `test.sh`: teste offline com fixtures.
- Só abre http e https; um endereço interno só quando o host foi passado à mão (as URLs seguidas vêm das páginas);
  o corpo é cortado em 10 MB e um sitemap repetido é lido uma vez.
