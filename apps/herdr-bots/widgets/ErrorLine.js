import { div } from 'gpui-kit';

export function ErrorLine({ error, narrow }, t) {
  return div().id('bots.error').text_size(11).text_color(t.blocked).tooltip(error).child(narrow ? '!' : error);
}
