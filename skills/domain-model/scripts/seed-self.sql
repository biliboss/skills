BEGIN;
INSERT OR REPLACE INTO dm_domain(slug,name,purpose) VALUES ('domain-model','Domain Model','Modelar o domínio de um projeto direto no SQLite do dev-console: entidades, relações, comandos, eventos e o glossário, de rascunho a real.');
INSERT OR REPLACE INTO dm_entity(domain,name,kind,definition) VALUES
('domain-model','Domain','aggregate','Um domínio modelado; raiz de tudo o que está abaixo.'),
('domain-model','Entity','entity','Uma coisa com identidade dentro do domínio (aggregate, entity ou value).'),
('domain-model','Attribute','value','Um campo de uma entidade, com tipo e obrigatoriedade.'),
('domain-model','Relation','value','Ligação nomeada entre duas entidades, com cardinalidade.'),
('domain-model','Command','entity','Uma intenção de um ator sobre uma entidade; emite um evento.'),
('domain-model','Event','entity','Um fato que aconteceu: muda o estado de uma entidade.'),
('domain-model','Term','value','Uma palavra do glossário, com o que evitar.');
INSERT OR REPLACE INTO dm_attribute(domain,entity,name,type,required) VALUES
('domain-model','Domain','slug','text',1),('domain-model','Domain','name','text',1),('domain-model','Domain','purpose','text',0),('domain-model','Domain','status','draft|real',1),
('domain-model','Entity','name','text',1),('domain-model','Entity','kind','aggregate|entity|value',1),('domain-model','Entity','definition','text',0),('domain-model','Entity','status','draft|real',1),
('domain-model','Attribute','name','text',1),('domain-model','Attribute','type','text',0),('domain-model','Attribute','required','bool',1),
('domain-model','Relation','verb','text',1),('domain-model','Relation','cardinality','1:1|1:N|N:1|N:N',0),
('domain-model','Command','name','text',1),('domain-model','Command','actor','text',0),('domain-model','Command','status','draft|real',1),
('domain-model','Event','name','category.event',1),('domain-model','Event','from_state','text',0),('domain-model','Event','to_state','text',0),('domain-model','Event','status','draft|real',1),
('domain-model','Term','term','text',1),('domain-model','Term','definition','text',1),('domain-model','Term','avoid','text',0);
INSERT OR REPLACE INTO dm_relation(domain,src,verb,dst,cardinality) VALUES
('domain-model','Domain','tem','Entity','1:N'),('domain-model','Domain','tem','Term','1:N'),
('domain-model','Entity','tem','Attribute','1:N'),('domain-model','Relation','liga','Entity','N:N'),
('domain-model','Command','age sobre','Entity','N:1'),('domain-model','Command','emite','Event','1:1'),('domain-model','Event','muda','Entity','N:1');
INSERT OR REPLACE INTO dm_command(domain,name,entity,actor,emits) VALUES
('domain-model','DraftDomain','Domain','agente','domain.drafted'),
('domain-model','AddEntity','Entity','agente','entity.added'),
('domain-model','AddAttribute','Attribute','agente','attribute.added'),
('domain-model','Relate','Relation','agente','relation.added'),
('domain-model','AddCommand','Command','agente','command.added'),
('domain-model','AddEvent','Event','agente','event.added'),
('domain-model','DefineTerm','Term','agente','term.defined'),
('domain-model','MarkReal','Domain','dono','domain.confirmed'),
('domain-model','Show','Domain','agente','domain.shown');
INSERT OR REPLACE INTO dm_event(domain,name,entity,from_state,to_state) VALUES
('domain-model','domain.drafted','Domain',NULL,'draft'),
('domain-model','entity.added','Entity',NULL,'draft'),
('domain-model','attribute.added','Attribute',NULL,'draft'),
('domain-model','relation.added','Relation',NULL,'draft'),
('domain-model','command.added','Command',NULL,'draft'),
('domain-model','event.added','Event',NULL,'draft'),
('domain-model','term.defined','Term',NULL,'draft'),
('domain-model','domain.confirmed','Domain','draft','real'),
('domain-model','domain.shown','Domain','draft','draft');
INSERT OR REPLACE INTO dm_term(domain,term,definition,avoid) VALUES
('domain-model','rascunho (draft)','Modelado, ainda não confirmado pelo dono nem visto no código.','proposta, ideia'),
('domain-model','real','Confirmado pelo dono ou rastreado no código.','pronto, final'),
('domain-model','evento','Fato no passado, nome category.event.','ação, trigger'),
('domain-model','comando','Intenção no imperativo, emite um evento.','request');
COMMIT;
