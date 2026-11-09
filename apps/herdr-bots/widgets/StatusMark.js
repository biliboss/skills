import { div, svg } from 'gpui-kit';

export function StatusMark({ status }, t) {
  if (status === 'working') return svg('mods/workspace-chrome/spinner.svg').size(12).flex_none().text_color(t.working).spin(900);
  if (status === 'blocked' || status === 'done') return div().size(6).flex_none().rounded(3).bg(t[status]);
  return null;
}
