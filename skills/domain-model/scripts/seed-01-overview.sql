-- Phase 01 of the domain-model skill itself: 7 nodes, 7 edges. Read left to right: a Domain holds Entities and
-- Terms; a Command acts on an Entity and emits an Event that changes it.
BEGIN;
DELETE FROM "01_overview_diagram" WHERE domain='domain-model';
INSERT INTO "01_overview_diagram"(domain,pos,row,item,kind,note) VALUES
('domain-model',1,'node','Domain','aggregate','O domínio modelado; raiz de tudo'),
('domain-model',2,'node','Entity','entity','Coisa com identidade no domínio'),
('domain-model',3,'node','Attribute','value','Campo de uma entidade'),
('domain-model',4,'node','Relation','value','Ligação nomeada entre entidades'),
('domain-model',5,'node','Command','entity','Intenção de um ator'),
('domain-model',6,'node','Event','entity','Fato que muda o estado'),
('domain-model',7,'node','Term','value','Palavra do glossário');
INSERT INTO "01_overview_diagram"(domain,pos,row,item,verb,target,cardinality) VALUES
('domain-model',10,'edge','Domain','tem','Entity','1:N'),
('domain-model',11,'edge','Domain','tem','Term','1:N'),
('domain-model',12,'edge','Entity','tem','Attribute','1:N'),
('domain-model',13,'edge','Relation','liga','Entity','N:N'),
('domain-model',14,'edge','Command','age sobre','Entity','N:1'),
('domain-model',15,'edge','Command','emite','Event','1:1'),
('domain-model',16,'edge','Event','muda','Entity','N:1');
COMMIT;
