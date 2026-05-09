import React, { useState, useEffect, useCallback, useRef } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge
} from 'reactflow';
import { Layers, Save, RefreshCw, Terminal, X } from 'lucide-react';

const App = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [taskName, setTaskName] = useState('001_fibonacci');
  const [status, setStatus] = useState('stopped');
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [logs, setLogs] = useState('');
  const logEndRef = useRef<HTMLDivElement>(null);

  const fetchGraph = async () => {
    try {
      const response = await fetch(`/api/tasks/${taskName}/graph`);
      if (!response.ok) return;
      const data = await response.json();
      
      if (!data || !data.nodes) return;

      const rfNodes = data.nodes.map((n: any, idx: number) => ({
        id: n.id,
        data: { label: n.id.toUpperCase(), ...n },
        position: { x: 250, y: idx * 100 },
        style: { background: '#333', color: '#fff', border: '1px solid #777', borderRadius: '8px', padding: '10px' }
      }));
      // ...
      
      const rfEdges = data.edges.map((e: any) => ({
        id: `e-${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        animated: false,
        style: { stroke: '#888' }
      }));

      data.conditional_edges.forEach((ce: any) => {
        Object.values(ce.mapping).forEach((target: any) => {
          if (target === '__end__') return;
          rfEdges.push({
            id: `ce-${ce.source}-${target}`,
            source: ce.source,
            target: target,
            label: 'conditional',
            animated: false,
            style: { stroke: '#f1c40f', strokeDasharray: '5,5' }
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
        // Fetch Node Status
        const sResponse = await fetch(`/api/tasks/${taskName}/status`);
        const sData = await sResponse.json();
        
        if (sData && sData.nodes) {
            setNodes((nds) => nds.map(node => {
               const s = sData.nodes[node.id];
               if (!s) return node;
               let color = '#333';
               if (s.status === 'success') color = '#1b5e20';
               if (s.status === 'running') color = '#fbc02d';
               return { ...node, style: { ...node.style, background: color } };
            }));
        }

        // Fetch Logs
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
    fetchGraph();
    const interval = setInterval(fetchStatusAndLogs, 2000);
    return () => clearInterval(interval);
  }, [taskName, selectedNode]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const onRun = async () => {
    setStatus('launching');
    try {
      await fetch(`/api/tasks/${taskName}/run`, { method: 'POST' });
      setTimeout(() => setStatus('running'), 3000);
    } catch (e) {
      setStatus('stopped');
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

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: '#1a1a1a', color: '#fff' }}>
      <header style={{ padding: '10px 20px', background: '#222', borderBottom: '1px solid #444', display: 'flex', alignItems: 'center', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Layers size={20} color="#3498db" />
          <h2 style={{ margin: 0, fontSize: '18px' }}>RALPH Studio</h2>
          <a href="http://localhost:8501" style={{ fontSize: '12px', color: '#888', textDecoration: 'none', marginLeft: '10px' }}>← Back to Dashboard</a>
        </div>

        <div style={{ flex: 1, display: 'flex', justifyContent: 'center', gap: '10px' }}>
           <button 
             onClick={onRun}
             disabled={status === 'launching'}
             style={{ background: status === 'launching' ? '#555' : '#2ecc71', color: '#fff', border: 'none', padding: '6px 15px', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}
           >
             {status === 'launching' ? '🚀 Launching...' : '▶️ Play'}
           </button>
           <button 
             onClick={() => onControl('pause')}
             style={{ background: '#f1c40f', color: '#000', border: 'none', padding: '6px 15px', borderRadius: '4px', cursor: 'pointer' }}
           >
             ⏸️ Pause
           </button>
           <button 
             onClick={() => onControl('abort')}
             style={{ background: '#e74c3c', color: '#fff', border: 'none', padding: '6px 15px', borderRadius: '4px', cursor: 'pointer' }}
           >
             ⏹️ Abort
           </button>
        </div>

        <select 
          value={taskName} 
          onChange={(e) => setTaskName(e.target.value)}
          style={{ background: '#333', color: '#fff', border: '1px solid #555', padding: '5px 10px', borderRadius: '4px' }}
        >
          <option value="001_fibonacci">001_fibonacci</option>
          <option value="002_meta_test">002_meta_test</option>
        </select>
        <button onClick={fetchGraph} style={{ background: 'transparent', border: 'none', color: '#888', cursor: 'pointer' }}>
          <RefreshCw size={18} />
        </button>
        <button 
          onClick={saveGraph}
          style={{ background: '#3498db', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}
        >
          <Save size={18} />
          Save Graph
        </button>
      </header>
      
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, display: 'flex' }}>
            <div style={{ flex: 1 }}>
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  onNodeClick={onNodeClick}
                  fitView
                  style={{ background: '#1a1a1a' }}
                >
                  <Background color="#333" gap={16} />
                  <Controls />
                  <MiniMap nodeColor={() => '#444'} style={{ background: '#222' }} />
                </ReactFlow>
            </div>
            
            {selectedNode && (
                <div style={{ width: '300px', background: '#222', borderLeft: '1px solid #444', padding: '20px', overflowY: 'auto', color: '#eee' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ margin: 0, color: '#3498db' }}>{selectedNode.id.toUpperCase()}</h3>
                        <button onClick={() => setSelectedNode(null)} style={{ background: 'transparent', border: 'none', color: '#888', cursor: 'pointer' }}><X size={18}/></button>
                    </div>
                    <hr style={{ border: '0.5px solid #444', margin: '15px 0' }} />
                    <div style={{ fontSize: '13px' }}>
                        <p><strong>Module:</strong> {selectedNode.data.module}</p>
                        <p><strong>Function:</strong> {selectedNode.data.func}</p>
                    </div>
                </div>
            )}
        </div>
        
        {/* Bottom Console Panel */}
        <div style={{ height: '200px', background: '#111', borderTop: '2px solid #333', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '5px 20px', background: '#222', display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px', borderBottom: '1px solid #333' }}>
                <Terminal size={14} color="#3498db" />
                <span>{selectedNode ? `Node Trace: ${selectedNode.id.toUpperCase()}` : 'General Console Output'}</span>
                {selectedNode && <button onClick={() => setSelectedNode(null)} style={{ marginLeft: 'auto', background: 'transparent', border: 'none', color: '#555', cursor: 'pointer', fontSize: '11px' }}>Switch to General</button>}
            </div>
            <div style={{ flex: 1, padding: '10px 20px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '12px', color: '#aaa', whiteSpace: 'pre-wrap' }}>
                {logs}
                <div ref={logEndRef} />
            </div>
        </div>
      </div>
    </div>
  );
};

export default App;
