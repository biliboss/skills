# Prior art

| Fonte | O que faz | A ideia levada |
|---|---|---|
| [Nango](https://github.com/NangoHQ/nango) | OAuth e integrações como serviço | conexão por conta; o provedor renova; desenho de referência |
| [Composio](https://composio.dev) | autenticação e ferramentas para agentes, hospedado | o agente precisa de uma identidade por conta; rejeitado por ser terceiro no caminho do token |
| [oama](https://github.com/pdobsan/oama) | credenciais OAuth de e-mail | gerente leve por CLI; só e-mail |
| [oauth2c](https://github.com/cloudentity/oauth2c) | obtém tokens OAuth 2.0 | plano B para provedor sem CLI oficial |
| [gws](https://github.com/googleworkspace/cli) | CLI do Google Workspace | login, renovação e token cifrado delegados a ela |
| oauth2l (Google) | utilitário de tokens Google | só Google; link não conferido |
| AuthLM | auth de provedores de IA | só IA; link não conferido |
| [RFC 6749](https://www.rfc-editor.org/rfc/rfc6749) · [RFC 7636](https://www.rfc-editor.org/rfc/rfc7636) | OAuth 2.0 · PKCE | o fluxo |
