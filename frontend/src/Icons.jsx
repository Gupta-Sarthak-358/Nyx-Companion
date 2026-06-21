import React from 'react';

const h = React.createElement;

const createIcon = (paths) => {
  const Icon = ({ size = 24, className = '', ...props }) =>
    h('svg', {
      xmlns: 'http://www.w3.org/2000/svg',
      width: size,
      height: size,
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: 'currentColor',
      strokeWidth: '2',
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
      className,
      ...props
    }, ...paths.map((p, i) => h(p.tag || 'path', { key: i, ...p.attrs })));
  return Icon;
};

const p = (tag, attrs) => ({ tag, attrs });

export const Icons = {
  Mic: createIcon([
    p('path', { d: 'M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z' }),
    p('path', { d: 'M19 10v1a7 7 0 0 1-14 0v-1' }),
    p('line', { x1: '12', x2: '12', y1: '19', y2: '22' }),
  ]),
  Send: createIcon([
    p('line', { x1: '22', x2: '11', y1: '2', y2: '13' }),
    p('polygon', { points: '22 2 15 22 11 13 2 9 22 2' }),
  ]),
  Settings: createIcon([
    p('path', { d: 'M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z' }),
    p('circle', { cx: '12', cy: '12', r: '3' }),
  ]),
  Retry: createIcon([
    p('path', { d: 'M21.5 2v6h-6' }),
    p('path', { d: 'M21.34 15.57a10 10 0 1 1-.57-8.38' }),
  ]),
  Leave: createIcon([
    p('path', { d: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4' }),
    p('polyline', { points: '16 17 21 12 16 7' }),
    p('line', { x1: '21', x2: '9', y1: '12', y2: '12' }),
  ]),
  Knowledge: createIcon([
    p('path', { d: 'M4 19.5A2.5 2.5 0 0 1 6.5 17H20' }),
    p('path', { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z' }),
  ]),
  Diagnostics: createIcon([
    p('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2', ry: '2' }),
    p('path', { d: 'M9 12h3l2-4 2 8 2-4h2' }),
  ]),
  Close: createIcon([
    p('line', { x1: '18', x2: '6', y1: '6', y2: '18' }),
    p('line', { x1: '6', x2: '18', y1: '6', y2: '18' }),
  ]),
  Upload: createIcon([
    p('path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }),
    p('polyline', { points: '17 8 12 3 7 8' }),
    p('line', { x1: '12', x2: '12', y1: '3', y2: '15' }),
  ]),
  Delete: createIcon([
    p('polyline', { points: '3 6 5 6 21 6' }),
    p('path', { d: 'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2' }),
  ]),
  Sparkles: createIcon([
    p('path', { d: 'm12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z' }),
  ]),
  BookOpen: createIcon([
    p('path', { d: 'M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z' }),
    p('path', { d: 'M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z' }),
  ]),
  Camera: createIcon([
    p('path', { d: 'M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z' }),
    p('circle', { cx: '12', cy: '13', r: '4' }),
  ]),
  Check: createIcon([
    p('polyline', { points: '20 6 9 17 4 12' }),
  ]),
  Moon: createIcon([
    p('path', { d: 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z' }),
  ]),
  Bot: createIcon([
    p('rect', { x: '3', y: '11', width: '18', height: '10', rx: '2' }),
    p('circle', { cx: '12', cy: '5', r: '2' }),
    p('path', { d: 'M9 14h6' }),
    p('path', { d: 'M9 17h3' }),
  ]),
  NyxCore: createIcon([
    p('path', { d: 'M7 21V3L17 21V3' }),
  ]),
  Chart: createIcon([
    p('line', { x1: '18', x2: '18', y1: '20', y2: '10' }),
    p('line', { x1: '12', x2: '12', y1: '20', y2: '4' }),
    p('line', { x1: '6', x2: '6', y1: '20', y2: '14' }),
  ]),
  Message: createIcon([
    p('path', { d: 'M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z' }),
  ]),
  Interview: createIcon([
    p('path', { d: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' }),
    p('polyline', { points: '14 2 14 8 20 8' }),
    p('line', { x1: '16', x2: '8', y1: '13', y2: '13' }),
    p('line', { x1: '16', x2: '8', y1: '17', y2: '17' }),
    p('polyline', { points: '10 9 9 9 8 9' }),
  ]),
};
