import { div } from 'gpui-kit';

export function PanelTitle(t) {
  return div().id('bots.title').px(8).pt(10).pb(4).text_size(11.5).text_color(t.dim).child('Bots');
}
