'use client';

import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, MeshDistortMaterial, Sphere, Torus, Stars, Environment } from '@react-three/drei';
import * as THREE from 'three';

const QuantumParticle = ({ position, color, scale = 1 }: { position: [number, number, number]; color: string; scale?: number }) => {
  const ref = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (ref.current) {
      const t = state.clock.getElapsedTime();
      ref.current.position.y = position[1] + Math.sin(t * 2 + position[0]) * 0.2;
      ref.current.rotation.x = t * 0.5;
      ref.current.rotation.z = t * 0.3;
    }
  });

  return (
    <Sphere ref={ref} args={[1, 32, 32]} position={position} scale={scale}>
      <MeshDistortMaterial
        color={color}
        envMapIntensity={1}
        clearcoat={1}
        clearcoatRoughness={0}
        metalness={0.5}
        distort={0.4}
        speed={2}
      />
    </Sphere>
  );
};

const MacroscopicWave = () => {
  const ref = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (ref.current) {
       const t = state.clock.getElapsedTime();
       ref.current.rotation.x = Math.sin(t * 0.2) * 0.2;
       ref.current.rotation.y = t * 0.1;
    }
  });

  return (
    <Torus ref={ref} args={[3, 0.1, 16, 100]} rotation={[Math.PI / 2, 0, 0]}>
      <meshStandardMaterial color="#C5A059" emissive="#C5A059" emissiveIntensity={0.5} transparent opacity={0.6} wireframe />
    </Torus>
  );
}

export default function QuantumSceneInner({ className }: { className?: string }) {
  return (
    <div className={`absolute inset-0 z-0 opacity-60 pointer-events-none ${className || ''}`}>
      <Canvas
        camera={{ position: [0, 0, 6], fov: 45 }}
        gl={{
          antialias: true,
          preserveDrawingBuffer: true,
          powerPreference: "default"
        }}
        onCreated={({ gl }) => {
          gl.setClearColor('#000000', 0);
        }}
      >
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} />
        <Float speed={1.5} rotationIntensity={0.2} floatIntensity={0.5}>
          <QuantumParticle position={[0, 0, 0]} color="#4F46E5" scale={1.2} />
          <MacroscopicWave />
        </Float>

        <Float speed={2} rotationIntensity={0.5} floatIntensity={1}>
           <QuantumParticle position={[-3, 1, -2]} color="#9333EA" scale={0.5} />
           <QuantumParticle position={[3, -1, -3]} color="#C5A059" scale={0.6} />
        </Float>

        <Environment preset="city" />
        <Stars radius={100} depth={50} count={1000} factor={4} saturation={0} fade speed={1} />
      </Canvas>
    </div>
  );
}
