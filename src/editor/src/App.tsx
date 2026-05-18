import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  MarkerType
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Layers, Save, RefreshCw, Terminal, X, Play, Pause, Square, Activity, Cloud, Zap } from 'lucide-react';

const App = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [taskName, setTaskName] = useState('001_fibonacci');
  const [engineStatus, setEngineStatus] = useState('stopped');
  const [isEscalated, setIsEscalated] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [logs, setLogs] = useState('');
  const [availableTasks, setAvailableTasks] = useState<string[]>(['001_fibonacci', '002_meta_test']);
  const logEndRef = useRef<HTMLDivElement>(null);

  const fetchTasks = async () => {
    try {
      const response = await fetch('/api/tasks');
      if (response.ok) {
        const data = await response.json();
        setAvailableTasks(data);
      }
    } catch (e) { console.warn("Failed to fetch tasks list"); }
  };

  const fetchGraph = async () => {
    try {
      const response = await fetch(`/api/tasks/${taskName}/graph`);
      if (!response.ok) return;
      const data = await response.json();
      
      if (!data || !data.nodes) return;

      const rfNodes = data.nodes.map((n: any, idx: number) => {
        // Simple layout logic: entry point at top, others spread out
        const isEntry = n.id === data.entry_point;
        return {
          id: n.id,
          data: { label: n.id.toUpperCase(), ...n },
          position: { x: isEntry ? 400 : 200 + (idx % 3) * 250, y: idx * 120 + 50 },
          style: { 
            background: '#1e1e1e', 
            color: '#fff', 
            border: '2px solid #333', 
            borderRadius: '12px', 
            padding: '15px',
            width: 180,
            fontSize: '12px',
            boxShadow: '0 4px 15px rgba(0,0,0,0.5)',
            transition: 'all 0.3s ease'
          }
        };
      });
      
      const rfEdges = data.edges.map((e: any) => ({
        id: `e-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        animated: false,
        style: { stroke: '#555', strokeWidth: 2 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#555' }
      }));

      data.conditional_edges.forEach((ce: any) => {
        Object.entries(ce.mapping).forEach(([key, target]: [string, any]) => {
          if (target === '__end__') return;
          rfEdges.push({
            id: `ce-${ce.source}-${target}`,
            source: ce.source,
            target: target,
            label: key,
            labelStyle: { fill: '#888', fontSize: 10 },
            animated: false,
            style: { stroke: '#f1c40f', strokeDasharray: '5,5', opacity: 0.6 },
            markerEnd: { type: MarkerType.ArrowClosed, color: '#f1c40f' }
          });
        });
      });

      setNodes(rfNodes);
      setEdges(rfEdges);
    } catch (error) {
      console.error('Failed to fetch graph:', error);
    }
  };

  const fetchStatusAndLogs = async () => {
    try {
        const sResponse = await fetch(`/api/tasks/${taskName}/status`);
        const sData = await sResponse.json();
        
        if (sData && sData.nodes) {
            setNodes((nds) => nds.map(node => {
               const s = sData.nodes[node.id];
               if (!s) return { ...node, style: { ...node.style, background: '#1e1e1e', borderColor: '#333', boxShadow: 'none' } };
               
               let color = '#1e1e1e';
               let borderColor = '#333';
               let boxShadow = 'none';
               let animated = false;

               if (s.status === 'success') {
                 color = '#064e3b'; 
                 borderColor = '#10b981';
                 boxShadow = '0 0 15px rgba(16, 185, 129, 0.4)';
               } else if (s.status === 'running') {
                 color = '#451a03';
                 borderColor = '#f59e0b';
                 boxShadow = '0 0 20px rgba(245, 158, 11, 0.6)';
                 animated = true;
               } else if (s.status === 'failed') {
                 color = '#450a0a';
                 borderColor = '#ef4444';
                 boxShadow = '0 0 15px rgba(239, 68, 68, 0.4)';
               }

               return { 
                 ...node, 
                 style: { ...node.style, background: color, borderColor: borderColor, boxShadow: boxShadow },
                 className: animated ? 'pulse-node' : ''
               };
            }));

            // Check for escalation
            if (sData.status === 'running') setEngineStatus('running');
            else if (sData.status === 'stopped') setEngineStatus('stopped');
            setIsEscalated(!!sData.escalated);
        }

        const logUrl = selectedNode 
            ? `/api/tasks/${taskName}/logs/${selectedNode.id}`
            : `/api/tasks/${taskName}/logs/console`;
        const lResponse = await fetch(logUrl);
        const lData = await lResponse.json();
        if (lData && lData.content) {
            setLogs(lData.content);
        }
    } catch (e) {
        console.warn("Polling error:", e);
    }
  };

  useEffect(() => {
    fetchTasks();
    fetchGraph();
    const interval = setInterval(fetchStatusAndLogs, 1500);
    return () => clearInterval(interval);
  }, [taskName, selectedNode]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const onRun = async () => {
    setEngineStatus('launching');
    try {
      await fetch(`/api/tasks/${taskName}/run`, { method: 'POST' });
      setTimeout(() => setEngineStatus('running'), 2000);
    } catch (e) {
      setEngineStatus('stopped');
      alert('Failed to launch task.');
    }
  };

  const onControl = async (command: string) => {
    await fetch(`/api/tasks/${taskName}/control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command })
    });
  };

  const onConnect = useCallback((params: Connection | Edge) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  const onNodeClick = (_: any, node: any) => {
    setSelectedNode(node);
  };

  const saveGraph = async () => {
    try {
      const graphData = {
        nodes: nodes.map(n => ({ id: n.id, ...n.data })),
        edges: edges.filter(e => !e.label).map(e => ({ source: e.source, target: e.target })),
        conditional_edges: [],
        entry_point: "planner"
      };
      
      const response = await fetch(`/api/tasks/${taskName}/graph`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(graphData)
      });
      if (response.ok) alert('Graph saved successfully!');
    } catch (error) {
      console.error('Failed to save graph:', error);
    }
  };

  const formatLog = (text: string) => {
    return text.split('\n').map((line, i) => {
      let color = '#aaa';
      if (line.includes('[00:')) color = '#3498db';
      if (line.includes('PASS')) color = '#2ecc71';
      if (line.includes('TIMEOUT')) color = '#f1c40f';
      if (line.includes('CRASH') || line.includes('🚨')) color = '#e74c3c';
      if (line.includes('aider') || line.includes('gemini')) color = '#9b59b6';
      
      return <div key={i} style={{ color }}>{line}</div>;
    });
  };

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: '#0f172a', color: '#f8fafc', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <style>{`
        @keyframes pulse {
          0% { border-color: #f59e0b; box-shadow: 0 0 5px rgba(245, 158, 11, 0.4); }
          50% { border-color: #fbbf24; box-shadow: 0 0 25px rgba(245, 158, 11, 0.8); }
          100% { border-color: #f59e0b; box-shadow: 0 0 5px rgba(245, 158, 11, 0.4); }
        }
        .pulse-node {
          animation: pulse 1.5s infinite ease-in-out;
        }
        .glass-panel {
          background: rgba(30, 41, 59, 0.7);
          backdrop-filter: blur(12px);
          border: 1px solid rgba(255, 255, 255, 0.1);
        }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 10px; }
      `}</style>

      <header className="glass-panel" style={{ padding: '12px 24px', display: 'flex', alignItems: 'center', gap: '24px', zIndex: 10, boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ background: '#3b82f6', padding: '6px', borderRadius: '8px' }}>
            <Layers size={20} color="#fff" />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '18px', fontWeight: 700, letterSpacing: '-0.025em' }}>RALPH <span style={{ color: '#3b82f6' }}>STUDIO</span></h1>
            <a href="http://localhost:8501" style={{ fontSize: '11px', color: '#64748b', textDecoration: 'none', transition: 'color 0.2s' }}>Explorer Dashboard &rarr;</a>
          </div>
        </div>

        <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px' }}>
           <div style={{ background: '#1e293b', padding: '4px', borderRadius: '10px', display: 'flex', gap: '4px' }}>
             <button 
               onClick={onRun}
               disabled={engineStatus === 'launching' || engineStatus === 'running'}
               style={{ background: engineStatus === 'running' ? '#064e3b' : '#10b981', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600 }}
             >
               <Play size={14} fill="currentColor" /> {engineStatus === 'launching' ? 'Launching...' : 'Run'}
             </button>
             <button 
               onClick={() => onControl('pause')}
               style={{ background: 'transparent', color: '#f59e0b', border: 'none', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}
             >
               <Pause size={14} fill="currentColor" /> Pause
             </button>
             <button 
               onClick={() => onControl('abort')}
               style={{ background: 'transparent', color: '#ef4444', border: 'none', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}
             >
               <Square size={14} fill="currentColor" /> Abort
             </button>
           </div>

           {isEscalated && (
             <div style={{ background: '#1e40af', color: '#bfdbfe', padding: '6px 12px', borderRadius: '20px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 600, border: '1px solid #3b82f6' }}>
               <Cloud size={14} /> Cloud Escalated
             </div>
           )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <select 
            value={taskName} 
            onChange={(e) => setTaskName(e.target.value)}
            style={{ background: '#1e293b', color: '#fff', border: '1px solid #334155', padding: '8px 12px', borderRadius: '8px', fontSize: '13px', cursor: 'pointer' }}
          >
            {availableTasks.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button onClick={fetchGraph} style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer', transition: 'color 0.2s' }}>
            <RefreshCw size={18} />
          </button>
          <button 
            onClick={saveGraph}
            style={{ background: '#3b82f6', color: '#fff', border: 'none', padding: '8px 20px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px', fontWeight: 600 }}
          >
            <Save size={16} /> Save
          </button>
        </div>
      </header>
      
      <main style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        <div style={{ flex: 1, position: 'relative' }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              fitView
              style={{ background: '#0f172a' }}
            >
              <Background color="#334155" gap={20} size={1} />
              <Controls style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} />
              <MiniMap 
                nodeColor={(n) => {
                  if (n.className === 'pulse-node') return '#f59e0b';
                  return '#334155';
                }} 
                maskColor="rgba(15, 23, 42, 0.7)"
                style={{ background: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }} 
              />
            </ReactFlow>
            
            {/* Legend / Overlay */}
            <div style={{ position: 'absolute', bottom: 20, right: 20, pointerEvents: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
               <div style={{ background: 'rgba(30, 41, 59, 0.8)', padding: '10px 15px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', fontSize: '11px', display: 'flex', gap: '15px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: 8, height: 8, borderRadius: '2px', background: '#10b981' }}></div> Success</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: 8, height: 8, borderRadius: '2px', background: '#f59e0b' }}></div> Running</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><div style={{ width: 8, height: 8, borderRadius: '2px', background: '#ef4444' }}></div> Failed</div>
               </div>
            </div>
        </div>
        
        {/* Sidebar Info Panel */}
        {selectedNode && (
            <aside className="glass-panel" style={{ width: '320px', borderLeft: '1px solid rgba(255,255,255,0.1)', display: 'flex', flexDirection: 'column' }}>
                <div style={{ padding: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <Activity size={18} color="#3b82f6" />
                            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#fff' }}>{selectedNode.id.toUpperCase()}</h3>
                        </div>
                        <button onClick={() => setSelectedNode(null)} style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer' }}><X size={20}/></button>
                    </div>
                    
                    <div style={{ background: 'rgba(0,0,0,0.2)', padding: '15px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.05)' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
                            <div>
                                <label style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', fontWeight: 600 }}>Module</label>
                                <div style={{ color: '#cbd5e1', marginTop: '2px' }}>{selectedNode.data.module}</div>
                            </div>
                            <div>
                                <label style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', fontWeight: 600 }}>Function</label>
                                <div style={{ color: '#cbd5e1', marginTop: '2px' }}>{selectedNode.data.func}</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div style={{ flex: 1, padding: '0 24px 24px', overflowY: 'auto' }}>
                    <label style={{ color: '#64748b', fontSize: '11px', textTransform: 'uppercase', fontWeight: 600, display: 'block', marginBottom: '8px' }}>Node Data / Trace</label>
                    <div style={{ fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8', background: 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '8px', whiteSpace: 'pre-wrap' }}>
                        {logs.includes('{') ? logs : 'Select node in run to view trace data.'}
                    </div>
                </div>
            </aside>
        )}
      </main>
      
      {/* Footer Console */}
      <footer style={{ height: '240px', background: '#020617', borderTop: '1px solid #1e293b', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '8px 24px', background: '#0f172a', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '11px', fontWeight: 600, color: '#64748b', borderBottom: '1px solid #1e293b' }}>
              <Terminal size={14} />
              <span>{selectedNode ? `TRACE: ${selectedNode.id.toUpperCase()}` : 'ENGINE CONSOLE'}</span>
              <div style={{ flex: 1 }}></div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                {selectedNode && <button onClick={() => setSelectedNode(null)} style={{ background: 'transparent', border: 'none', color: '#3b82f6', cursor: 'pointer', fontSize: '11px' }}>Back to Console</button>}
                <Activity size={12} color={engineStatus === 'running' ? '#10b981' : '#64748b'} />
                <span style={{ color: engineStatus === 'running' ? '#10b981' : '#64748b' }}>{engineStatus.toUpperCase()}</span>
              </div>
          </div>
          <div style={{ flex: 1, padding: '16px 24px', overflowY: 'auto', fontFamily: '"JetBrains Mono", monospace', fontSize: '12px', color: '#cbd5e1', lineHeight: '1.6' }}>
              {formatLog(logs)}
              <div ref={logEndRef} />
          </div>
      </footer>
    </div>
  );
};

export default App;

