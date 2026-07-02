import React, { useEffect, useRef } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  securityLevel: 'loose',
  fontFamily: 'Inter, sans-serif'
});

export default function Mermaid({ chart }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (chart && containerRef.current) {
      const renderChart = async () => {
        try {
          const { svg } = await mermaid.render('mermaid-svg-' + Date.now(), chart);
          if (containerRef.current) {
            containerRef.current.innerHTML = svg;
          }
        } catch (error) {
          console.error('Mermaid rendering error', error);
          if (containerRef.current) {
            containerRef.current.innerHTML = `<pre class="text-red-400 text-xs">${chart}</pre>`;
          }
        }
      };
      renderChart();
    }
  }, [chart]);

  return <div ref={containerRef} className="overflow-auto w-full flex justify-center py-4" />;
}
