import { exec, readTextFile, home, props } from 'herdr';

export async function loadBots() {
  const path = props().registry ?? `${home()}/agents/bots.json`;
  const raw = await readTextFile(path);
  if (raw === null) throw new Error(`Cadastro ausente: ${path}`);
  const result = await exec('env', [`AG_HOME=${props().dataHome}`, `AG_BOTS_FILE=${path}`, props().opener, '--list']);
  if (result.code !== 0) throw new Error(result.stderr || 'Cadastro inválido');
  return JSON.parse(result.stdout).bots;
}

export async function openBot(bot) {
  const result = await exec('env', [`AG_HOME=${props().dataHome}`, `AG_BOTS_FILE=${props().registry}`, props().opener, '--focus', bot.id]);
  if (result.code !== 0) throw new Error(result.stderr || result.stdout);
}
