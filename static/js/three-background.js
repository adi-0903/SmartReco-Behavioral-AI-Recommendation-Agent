/**
 * SmartReco 3D Background System
 * Interactive particle field, neural network visualization, and geometric animations
 */
(function() {
    'use strict';

    let scene, camera, renderer, particles, neuralNetwork, geometryShapes;
    let mouseX = 0, mouseY = 0;
    let targetX = 0, targetY = 0;
    let animationId = null;
    let isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const CONFIG = {
        particleCount: 2000,
        neuralNodes: 80,
        neuralConnections: 120,
        geometryCount: 15,
        colors: {
            primary: 0x6366f1,
            secondary: 0xec4899,
            accent: 0x38bdf8,
            success: 0x10b981,
            particles: [0x6366f1, 0x38bdf8, 0xec4899, 0x10b981, 0xf59e0b]
        },
        speeds: {
            particle: 0.0005,
            neural: 0.001,
            geometry: 0.0008
        }
    };

    function init() {
        const canvas = document.getElementById('three-canvas');
        if (!canvas) return;

        if (isReducedMotion) {
            canvas.style.display = 'none';
            return;
        }

        setupScene(canvas);
        createParticleField();
        createNeuralNetwork();
        createGeometryShapes();
        setupEventListeners();
        animate();
    }

    function setupScene(canvas) {
        scene = new THREE.Scene();
        
        camera = new THREE.PerspectiveCamera(
            60, 
            window.innerWidth / window.innerHeight, 
            1, 
            1000
        );
        camera.position.z = 50;

        renderer = new THREE.WebGLRenderer({
            canvas: canvas,
            alpha: true,
            antialias: true,
            powerPreference: 'high-performance'
        });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setClearColor(0x000000, 0);

        window.addEventListener('resize', onResize);
    }

    function createParticleField() {
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(CONFIG.particleCount * 3);
        const colors = new Float32Array(CONFIG.particleCount * 3);
        const sizes = new Float32Array(CONFIG.particleCount);
        const velocities = new Float32Array(CONFIG.particleCount * 3);
        const alphas = new Float32Array(CONFIG.particleCount);

        for (let i = 0; i < CONFIG.particleCount; i++) {
            const radius = 30 + Math.random() * 40;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);

            positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i * 3 + 2] = radius * Math.cos(phi) - 20;

            const colorChoice = CONFIG.colors.particles[Math.floor(Math.random() * CONFIG.colors.particles.length)];
            const color = new THREE.Color(colorChoice);
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;

            sizes[i] = 0.5 + Math.random() * 2.5;
            alphas[i] = 0.1 + Math.random() * 0.6;

            velocities[i * 3] = (Math.random() - 0.5) * 0.02;
            velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.02;
            velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.02;
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
        geometry.setAttribute('alpha', new THREE.BufferAttribute(alphas, 1));
        geometry.setAttribute('velocity', new THREE.BufferAttribute(velocities, 3));

        const material = new THREE.PointsMaterial({
            size: 1.5,
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
            sizeAttenuation: true,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });

        particles = new THREE.Points(geometry, material);
        particles.userData = { velocities, alphas };
        scene.add(particles);
    }

    function createNeuralNetwork() {
        const group = new THREE.Group();
        const nodes = [];
        const connections = [];

        for (let i = 0; i < CONFIG.neuralNodes; i++) {
            const radius = 15 + Math.random() * 25;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);

            const x = radius * Math.sin(phi) * Math.cos(theta);
            const y = radius * Math.sin(phi) * Math.sin(theta);
            const z = radius * Math.cos(phi) - 10;

            const nodeGeometry = new THREE.SphereGeometry(0.3 + Math.random() * 0.4, 12, 12);
            const nodeMaterial = new THREE.MeshBasicMaterial({
                color: new THREE.Color(CONFIG.colors.particles[Math.floor(Math.random() * CONFIG.colors.particles.length)]),
                transparent: true,
                opacity: 0.7,
                blending: THREE.AdditiveBlending
            });
            const node = new THREE.Mesh(nodeGeometry, nodeMaterial);
            node.position.set(x, y, z);
            node.userData = {
                originalPosition: new THREE.Vector3(x, y, z),
                speed: 0.0005 + Math.random() * 0.001,
                phase: Math.random() * Math.PI * 2
            };
            group.add(node);
            nodes.push(node);
        }

        for (let i = 0; i < CONFIG.neuralConnections; i++) {
            const nodeA = nodes[Math.floor(Math.random() * nodes.length)];
            const nodeB = nodes[Math.floor(Math.random() * nodes.length)];
            if (nodeA === nodeB) continue;

            const distance = nodeA.position.distanceTo(nodeB.position);
            if (distance > 35) continue;

            const points = [
                nodeA.position.clone(),
                nodeB.position.clone()
            ];
            const lineGeometry = new THREE.BufferGeometry().setFromPoints(points);
            const lineMaterial = new THREE.LineBasicMaterial({
                color: 0x6366f1,
                transparent: true,
                opacity: 0.15,
                blending: THREE.AdditiveBlending
            });
            const line = new THREE.Line(lineGeometry, lineMaterial);
            line.userData = { nodeA, nodeB, originalOpacity: 0.15 };
            group.add(line);
            connections.push(line);
        }

        neuralNetwork = { group, nodes, connections };
        scene.add(group);
    }

    function createGeometryShapes() {
        const group = new THREE.Group();
        const geometries = [
            new THREE.TetrahedronGeometry(2),
            new THREE.OctahedronGeometry(1.8),
            new THREE.IcosahedronGeometry(1.5),
            new THREE.TorusGeometry(1.5, 0.4, 8, 16),
            new THREE.TorusKnotGeometry(1.2, 0.3, 64, 16)
        ];

        for (let i = 0; i < CONFIG.geometryCount; i++) {
            const geometry = geometries[Math.floor(Math.random() * geometries.length)];
            const material = new THREE.MeshPhysicalMaterial({
                color: CONFIG.colors.particles[Math.floor(Math.random() * CONFIG.colors.particles.length)],
                metalness: 0.3,
                roughness: 0.4,
                transparent: true,
                opacity: 0.15,
                transmission: 0.3,
                thickness: 0.5,
                clearcoat: 0.5,
                clearcoatRoughness: 0.2
            });
            const mesh = new THREE.Mesh(geometry, material);
            
            const radius = 25 + Math.random() * 20;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);

            mesh.position.set(
                radius * Math.sin(phi) * Math.cos(theta),
                radius * Math.sin(phi) * Math.sin(theta),
                radius * Math.cos(phi) - 15
            );

            mesh.userData = {
                rotationSpeed: new THREE.Vector3(
                    (Math.random() - 0.5) * 0.002,
                    (Math.random() - 0.5) * 0.002,
                    (Math.random() - 0.5) * 0.002
                ),
                orbitRadius: radius,
                orbitTheta: theta,
                orbitPhi: phi,
                orbitSpeed: 0.0002 + Math.random() * 0.0003,
                floatOffset: Math.random() * Math.PI * 2
            };
            group.add(mesh);
        }

        geometryShapes = group;
        scene.add(group);
    }

    function onResize() {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }

    function setupEventListeners() {
        document.addEventListener('mousemove', (e) => {
            mouseX = (e.clientX / window.innerWidth) * 2 - 1;
            mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
        });

        document.addEventListener('touchmove', (e) => {
            if (e.touches.length > 0) {
                mouseX = (e.touches[0].clientX / window.innerWidth) * 2 - 1;
                mouseY = -(e.touches[0].clientY / window.innerHeight) * 2 + 1;
            }
        }, { passive: true });

        window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
            isReducedMotion = e.matches;
            const canvas = document.getElementById('three-canvas');
            if (canvas) canvas.style.display = isReducedMotion ? 'none' : 'block';
        });
    }

    function animate() {
        if (isReducedMotion) return;

        animationId = requestAnimationFrame(animate);

        targetX += (mouseX - targetX) * 0.05;
        targetY += (mouseY - targetY) * 0.05;

        camera.position.x += (targetX * 8 - camera.position.x) * 0.02;
        camera.position.y += (targetY * 8 - camera.position.y) * 0.02;
        camera.lookAt(0, 0, -10);

        updateParticles();
        updateNeuralNetwork();
        updateGeometryShapes();

        renderer.render(scene, camera);
    }

    function updateParticles() {
        if (!particles) return;

        const positions = particles.geometry.attributes.position.array;
        const velocities = particles.userData.velocities;
        const alphas = particles.userData.alphas;
        const time = Date.now() * 0.001;

        for (let i = 0; i < CONFIG.particleCount; i++) {
            positions[i * 3] += velocities[i * 3];
            positions[i * 3 + 1] += velocities[i * 3 + 1];
            positions[i * 3 + 2] += velocities[i * 3 + 2];

            const dist = Math.sqrt(
                positions[i * 3] ** 2 + 
                positions[i * 3 + 1] ** 2 + 
                (positions[i * 3 + 2] + 20) ** 2
            );

            if (dist > 70) {
                const theta = Math.random() * Math.PI * 2;
                const phi = Math.acos(2 * Math.random() - 1);
                const radius = 30 + Math.random() * 10;

                positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
                positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
                positions[i * 3 + 2] = radius * Math.cos(phi) - 20;
            }

            alphas[i] = 0.1 + Math.sin(time * 2 + i * 0.1) * 0.3;
        }

        particles.geometry.attributes.position.needsUpdate = true;
        particles.geometry.attributes.alpha.needsUpdate = true;
        particles.material.opacity = 0.6 + Math.sin(time * 0.5) * 0.15;
    }

    function updateNeuralNetwork() {
        if (!neuralNetwork) return;

        const time = Date.now() * 0.001;
        const { nodes, connections } = neuralNetwork;

        nodes.forEach((node, i) => {
            const data = node.userData;
            node.position.x = data.originalPosition.x + Math.sin(time * data.speed + data.phase) * 2;
            node.position.y = data.originalPosition.y + Math.cos(time * data.speed + data.phase) * 2;
            node.position.z = data.originalPosition.z + Math.sin(time * data.speed * 0.7 + data.phase) * 1.5;

            node.material.opacity = 0.4 + Math.sin(time * 3 + i) * 0.2;
            node.scale.setScalar(0.8 + Math.sin(time * 2 + i) * 0.2);
        });

        connections.forEach((line) => {
            const { nodeA, nodeB } = line.userData;
            const positions = line.geometry.attributes.position.array;
            positions[0] = nodeA.position.x;
            positions[1] = nodeA.position.y;
            positions[2] = nodeA.position.z;
            positions[3] = nodeB.position.x;
            positions[4] = nodeB.position.y;
            positions[5] = nodeB.position.z;
            line.geometry.attributes.position.needsUpdate = true;

            const dist = nodeA.position.distanceTo(nodeB.position);
            line.material.opacity = Math.max(0.05, 0.2 * (1 - dist / 50));
        });

        neuralNetwork.group.rotation.y += 0.0001;
    }

    function updateGeometryShapes() {
        if (!geometryShapes) return;

        const time = Date.now() * 0.001;

        geometryShapes.children.forEach((mesh) => {
            const data = mesh.userData;

            mesh.rotation.x += data.rotationSpeed.x;
            mesh.rotation.y += data.rotationSpeed.y;
            mesh.rotation.z += data.rotationSpeed.z;

            data.orbitTheta += data.orbitSpeed;
            mesh.position.x = data.orbitRadius * Math.sin(data.orbitPhi) * Math.cos(data.orbitTheta);
            mesh.position.y = data.orbitRadius * Math.sin(data.orbitPhi) * Math.sin(data.orbitTheta) + Math.sin(time + data.floatOffset) * 3;
            mesh.position.z = data.orbitRadius * Math.cos(data.orbitPhi) - 15;

            mesh.material.opacity = 0.1 + Math.sin(time * 1.5 + data.floatOffset) * 0.05;
        });

        geometryShapes.rotation.y += 0.00005;
    }

    function destroy() {
        if (animationId) cancelAnimationFrame(animationId);
        if (renderer) renderer.dispose();
        if (scene) {
            scene.traverse((object) => {
                if (object.geometry) object.geometry.dispose();
                if (object.material) {
                    if (Array.isArray(object.material)) {
                        object.material.forEach(m => m.dispose());
                    } else {
                        object.material.dispose();
                    }
                }
            });
        }
    }

    window.ThreeBackground = { init, destroy };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();