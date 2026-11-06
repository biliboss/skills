-- Phase 01, diagram 'architecture': who writes the model, where it lives, how it reaches the screen. 9 nodes.
BEGIN;
DELETE FROM "01_overview_diagram" WHERE domain='domain-model' AND diagram='architecture';
INSERT INTO "01_overview_diagram"(domain,diagram,pos,row,item,kind,note) VALUES
('domain-model','architecture',1,'node','Agente','actor','Roda a skill domain-model'),
('domain-model','architecture',2,'node','models.py','code','O schema em SQLModel'),
('domain-model','architecture',3,'node','dev-console.sqlite','store','As tabelas dm_* e as fases'),
('domain-model','architecture',4,'node','Viewer SQLite','ui','Onde o dono lê as linhas'),
('domain-model','architecture',5,'node','console_model.py','code','Linhas viram Mermaid'),
('domain-model','architecture',6,'node','dev-console','service','O servidor FastHTML'),
('domain-model','architecture',7,'node','Browser','ui','O módulo base, aberto em /model'),
('domain-model','architecture',8,'node','DevConsole.app','ui','A janela nativa do Mac'),
('domain-model','architecture',9,'node','Dono','actor','Confirma: draft vira real');
INSERT INTO "01_overview_diagram"(domain,diagram,pos,row,item,verb,target) VALUES
('domain-model','architecture',10,'edge','models.py','cria tabelas','dev-console.sqlite'),
('domain-model','architecture',11,'edge','Agente','escreve linhas','dev-console.sqlite'),
('domain-model','architecture',12,'edge','Viewer SQLite','lê','dev-console.sqlite'),
('domain-model','architecture',13,'edge','console_model.py','lê só leitura','dev-console.sqlite'),
('domain-model','architecture',14,'edge','dev-console','carrega','console_model.py'),
('domain-model','architecture',15,'edge','Browser','abre /model','dev-console'),
('domain-model','architecture',16,'edge','DevConsole.app','mostra','Browser'),
('domain-model','architecture',17,'edge','Dono','olha','DevConsole.app'),
('domain-model','architecture',18,'edge','Dono','edita','Viewer SQLite');
COMMIT;
