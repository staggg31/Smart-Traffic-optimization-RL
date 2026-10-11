import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { Camera, Eye, Activity, Terminal, ChevronDown, ChevronUp, Info, Compass } from 'lucide-react';
import type { StepRecord } from '../types';

interface ThreeIntersectionProps {
  currentStep?: StepRecord | null;
  activePhase?: number; // 0: NS Green, 1: NS Yellow, 2: EW Green, 3: EW Yellow
  queueNS?: number;
  queueEW?: number;
  waitingTime?: number;
  isSimulating?: boolean;
}

interface VehicleEntity {
  id: string;
  name: string;
  type: 'bus' | 'car' | 'suv';
  mesh: THREE.Group;
  direction: 'N_to_S' | 'S_to_N' | 'W_to_E' | 'E_to_W';
  laneOffset: number;
  length: number;
  targetSpeed: number; // in world units per second (m/s ~ 45-55 km/h)
  currentSpeed: number;
  pos: number;
  state: 'CRUISING' | 'DECELERATING' | 'STOPPED_SIGNAL' | 'QUEUED';
  wheelNodes: THREE.Object3D[];
  wheelRadius: number;
  wheelSpinAxis: 'x' | 'z';
}

export const ThreeIntersection: React.FC<ThreeIntersectionProps> = ({
  currentStep,
  activePhase = 0,
  queueNS = 0.4,
  queueEW = 0.3,
  waitingTime: _waitingTime = 1.0,
  isSimulating = false,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [cameraView, setCameraView] = useState<'cinematic' | 'top' | 'driver'>('cinematic');
  const [showDiagnostics, setShowDiagnostics] = useState<boolean>(false);
  const [assetsLoaded, setAssetsLoaded] = useState<boolean>(false);

  // Diagnostic state updated throttled to ~10Hz
  const [diagInfo, setDiagInfo] = useState<{
    animTime: number;
    fps: number;
    deltaMs: number;
    phaseLabel: string;
    nsState: 'GREEN' | 'YELLOW' | 'RED';
    ewState: 'GREEN' | 'YELLOW' | 'RED';
    mode: 'AUTONOMOUS_CYCLE' | 'TRACI_REPLAY';
    vehicles: { id: string; name: string; pos: number; speed: number; state: string }[];
  }>({
    animTime: 0,
    fps: 60,
    deltaMs: 16.6,
    phaseLabel: 'INITIALIZING',
    nsState: 'GREEN',
    ewState: 'RED',
    mode: 'AUTONOMOUS_CYCLE',
    vehicles: [],
  });

  // Mutable refs to prevent React closure staleness inside requestAnimationFrame
  const propsRef = useRef({
    currentStep,
    activePhase,
    isSimulating,
  });
  useEffect(() => {
    propsRef.current = { currentStep, activePhase, isSimulating };
  });

  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const signalMatsRef = useRef<{
    nsRed: THREE.MeshStandardMaterial;
    nsYellow: THREE.MeshStandardMaterial;
    nsGreen: THREE.MeshStandardMaterial;
    ewRed: THREE.MeshStandardMaterial;
    ewYellow: THREE.MeshStandardMaterial;
    ewGreen: THREE.MeshStandardMaterial;
  } | null>(null);

  const vehiclesRef = useRef<VehicleEntity[]>([]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // 1. Scene & Daylight Sky Environment
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf1f5f9);
    scene.fog = new THREE.FogExp2(0xf1f5f9, 0.005);

    // 2. Camera Setup — Focused Cinematic Three-Quarter Default View
    const width = container.clientWidth;
    const height = container.clientHeight || 500;
    const camera = new THREE.PerspectiveCamera(36, width / height, 1, 500);
    cameraRef.current = camera;

    // Focused orbit: closer framing (radius 44) makes vehicles visually prominent and commanding
    let spherical = { radius: 44, theta: Math.PI / 4.0, phi: Math.PI / 3.1 };
    const updateCameraPos = () => {
      camera.position.x = spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta);
      camera.position.y = spherical.radius * Math.cos(spherical.phi);
      camera.position.z = spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta);
      camera.lookAt(0, 0.8, 0);
    };
    updateCameraPos();

    // 3. High-Performance WebGL Renderer with ACES Tone Mapping & Soft Shadows
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // 4. Natural Daylight Sun and Skylight (Calibrated to prevent blowout)
    const sunLight = new THREE.DirectionalLight(0xfffbf0, 1.65);
    sunLight.position.set(40, 55, 32);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    sunLight.shadow.camera.near = 10;
    sunLight.shadow.camera.far = 150;
    sunLight.shadow.camera.left = -40;
    sunLight.shadow.camera.right = 40;
    sunLight.shadow.camera.top = 40;
    sunLight.shadow.camera.bottom = -40;
    sunLight.shadow.bias = -0.0006;
    sunLight.shadow.normalBias = 0.02;
    scene.add(sunLight);

    const hemiLight = new THREE.HemisphereLight(0xe0f2fe, 0xcfd8dc, 0.35);
    scene.add(hemiLight);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.20);
    scene.add(ambientLight);

    // 5. Urban Base Ground & Sidewalk Plazas
    const groundGeo = new THREE.PlaneGeometry(130, 130);
    const groundMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.88 });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.05;
    ground.receiveShadow = true;
    scene.add(ground);

    // 6. Realistic Asphalt Roadways (22m wide dual-lane approaches)
    const roadWidth = 22.0;
    const roadLength = 110.0;
    const asphaltMat = new THREE.MeshStandardMaterial({
      color: 0x191e24,
      roughness: 0.85,
      metalness: 0.05,
    });

    // North-South Road
    const nsRoadGeo = new THREE.PlaneGeometry(roadWidth, roadLength);
    const nsRoad = new THREE.Mesh(nsRoadGeo, asphaltMat);
    nsRoad.rotation.x = -Math.PI / 2;
    nsRoad.position.y = 0.01;
    nsRoad.receiveShadow = true;
    scene.add(nsRoad);

    // East-West Road
    const ewRoadGeo = new THREE.PlaneGeometry(roadLength, roadWidth);
    const ewRoad = new THREE.Mesh(ewRoadGeo, asphaltMat);
    ewRoad.rotation.x = -Math.PI / 2;
    ewRoad.position.y = 0.01;
    ewRoad.receiveShadow = true;
    scene.add(ewRoad);

    // Central Intersection Patch
    const interGeo = new THREE.PlaneGeometry(roadWidth, roadWidth);
    const interPatch = new THREE.Mesh(interGeo, asphaltMat);
    interPatch.rotation.x = -Math.PI / 2;
    interPatch.position.y = 0.015;
    interPatch.receiveShadow = true;
    scene.add(interPatch);

    // 7. Raised 3D Concrete Curbs around Quadrant Sidewalks
    const curbMat = new THREE.MeshStandardMaterial({
      color: 0x94a3b8, // Defined stone curb border
      roughness: 0.65,
      metalness: 0.15,
    });
    const sidewalkMat = new THREE.MeshStandardMaterial({
      color: 0xdbe2ea, // Subtle urban concrete
      roughness: 0.85,
    });

    const createQuadrantSidewalk = (minX: number, maxX: number, minZ: number, maxZ: number) => {
      const w = maxX - minX;
      const d = maxZ - minZ;
      const cx = (minX + maxX) / 2;
      const cz = (minZ + maxZ) / 2;

      // Sidewalk slab
      const slabGeo = new THREE.BoxGeometry(w, 0.16, d);
      const slab = new THREE.Mesh(slabGeo, sidewalkMat);
      slab.position.set(cx, 0.08, cz);
      slab.receiveShadow = true;
      scene.add(slab);

      // Beveled curb edging facing the street
      const curbH = 0.18;
      const curbW = 0.35;

      const curbXGeo = new THREE.BoxGeometry(w, curbH, curbW);
      const curbX = new THREE.Mesh(curbXGeo, curbMat);
      const curbXPos = cz > 0 ? minZ + curbW / 2 : maxZ - curbW / 2;
      curbX.position.set(cx, curbH / 2, curbXPos);
      curbX.castShadow = true;
      curbX.receiveShadow = true;
      scene.add(curbX);

      const curbZGeo = new THREE.BoxGeometry(curbW, curbH, d);
      const curbZ = new THREE.Mesh(curbZGeo, curbMat);
      const curbZPos = cx > 0 ? minX + curbW / 2 : maxX - curbW / 2;
      curbZ.position.set(curbZPos, curbH / 2, cz);
      curbZ.castShadow = true;
      curbZ.receiveShadow = true;
      scene.add(curbZ);
    };

    // 4 Quadrants
    createQuadrantSidewalk(-55, -roadWidth / 2, -55, -roadWidth / 2); // North-West
    createQuadrantSidewalk(roadWidth / 2, 55, -55, -roadWidth / 2);  // North-East
    createQuadrantSidewalk(-55, -roadWidth / 2, roadWidth / 2, 55);  // South-West
    createQuadrantSidewalk(roadWidth / 2, 55, roadWidth / 2, 55);   // South-East

    // 8. Road Markings: Double Yellow Medians, Dashed Lane Lines, Stop Bars
    const lineWhiteMat = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.4,
      metalness: 0.0,
    });
    const lineYellowMat = new THREE.MeshStandardMaterial({
      color: 0xf59e0b,
      roughness: 0.4,
      metalness: 0.0,
    });

    // Double Yellow Center Medians (North & South)
    [-1, 1].forEach((side) => {
      const zStart = side * 15.5;
      const zEnd = side * 52.0;
      const len = Math.abs(zEnd - zStart);
      const midZ = (zStart + zEnd) / 2;
      [-0.15, 0.15].forEach((offset) => {
        const lineGeo = new THREE.PlaneGeometry(0.12, len);
        const line = new THREE.Mesh(lineGeo, lineYellowMat);
        line.rotation.x = -Math.PI / 2;
        line.position.set(offset, 0.025, midZ);
        scene.add(line);
      });
    });

    // Double Yellow Center Medians (East & West)
    [-1, 1].forEach((side) => {
      const xStart = side * 15.5;
      const xEnd = side * 52.0;
      const len = Math.abs(xEnd - xStart);
      const midX = (xStart + xEnd) / 2;
      [-0.15, 0.15].forEach((offset) => {
        const lineGeo = new THREE.PlaneGeometry(len, 0.12);
        const line = new THREE.Mesh(lineGeo, lineYellowMat);
        line.rotation.x = -Math.PI / 2;
        line.position.set(midX, 0.025, offset);
        scene.add(line);
      });
    });

    // Dashed White Lane Dividers
    const createDashedLine = (x: number, isVertical: boolean, start: number, end: number) => {
      const step = 5.5;
      const dashLen = 2.6;
      for (let pos = start; pos <= end; pos += step) {
        const dashGeo = new THREE.PlaneGeometry(isVertical ? 0.14 : dashLen, isVertical ? dashLen : 0.14);
        const dash = new THREE.Mesh(dashGeo, lineWhiteMat);
        dash.rotation.x = -Math.PI / 2;
        if (isVertical) {
          dash.position.set(x, 0.025, pos);
        } else {
          dash.position.set(pos, 0.025, x);
        }
        scene.add(dash);
      }
    };

    createDashedLine(-5.2, true, -50, -16);
    createDashedLine(5.2, true, -50, -16);
    createDashedLine(-5.2, true, 16, 50);
    createDashedLine(5.2, true, 16, 50);

    createDashedLine(-5.2, false, -50, -16);
    createDashedLine(5.2, false, -50, -16);
    createDashedLine(-5.2, false, 16, 50);
    createDashedLine(5.2, false, 16, 50);

    // Transverse Stop Bars (at pos = 15.5m before crosswalk)
    const stopBarGeo = new THREE.PlaneGeometry(8.8, 0.85);
    const stopN = new THREE.Mesh(stopBarGeo, lineWhiteMat);
    stopN.rotation.x = -Math.PI / 2;
    stopN.position.set(-5.2, 0.028, -15.5);
    scene.add(stopN);

    const stopS = new THREE.Mesh(stopBarGeo, lineWhiteMat);
    stopS.rotation.x = -Math.PI / 2;
    stopS.position.set(5.2, 0.028, 15.5);
    scene.add(stopS);

    const stopW = new THREE.Mesh(stopBarGeo, lineWhiteMat);
    stopW.rotation.x = -Math.PI / 2;
    stopW.rotation.z = Math.PI / 2;
    stopW.position.set(-15.5, 0.028, 5.2);
    scene.add(stopW);

    const stopE = new THREE.Mesh(stopBarGeo, lineWhiteMat);
    stopE.rotation.x = -Math.PI / 2;
    stopE.rotation.z = Math.PI / 2;
    stopE.position.set(15.5, 0.028, -5.2);
    scene.add(stopE);

    // Crisp Matte Zebra Crosswalks
    const createCrosswalk = (centerX: number, centerZ: number, isHoriz: boolean) => {
      const group = new THREE.Group();
      const numStripes = 9;
      const stripeW = 0.8;
      const stripeL = 3.6;
      for (let i = 0; i < numStripes; i++) {
        const stripeGeo = new THREE.PlaneGeometry(isHoriz ? stripeL : stripeW, isHoriz ? stripeW : stripeL);
        const stripe = new THREE.Mesh(stripeGeo, lineWhiteMat);
        stripe.rotation.x = -Math.PI / 2;
        const offset = (i - numStripes / 2 + 0.5) * 1.8;
        if (isHoriz) {
          stripe.position.set(0, 0.028, offset);
        } else {
          stripe.position.set(offset, 0.028, 0);
        }
        group.add(stripe);
      }
      group.position.set(centerX, 0, centerZ);
      scene.add(group);
    };

    createCrosswalk(0, -13.5, false); // North crosswalk
    createCrosswalk(0, 13.5, false);  // South crosswalk
    createCrosswalk(-13.5, 0, true);  // West crosswalk
    createCrosswalk(13.5, 0, true);   // East crosswalk

    // 9. Intersection Focal Point: Corner plaza delineators (clean aesthetic without obstructing blank boxes)
    // Giant blank box buildings and primitive sphere trees removed per user requirements to keep intersection as clear focal point.

    // 10. Cantilever Signal Gantries with Glowing Emissive Lamps
    const poleMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.5, roughness: 0.45 });
    const housingMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.7 });

    const nsRedMat = new THREE.MeshStandardMaterial({ color: 0x7f1d1d, emissive: 0x000000, roughness: 0.3 });
    const nsYelMat = new THREE.MeshStandardMaterial({ color: 0x78350f, emissive: 0x000000, roughness: 0.3 });
    const nsGrnMat = new THREE.MeshStandardMaterial({ color: 0x064e3b, emissive: 0x000000, roughness: 0.3 });

    const ewRedMat = new THREE.MeshStandardMaterial({ color: 0x7f1d1d, emissive: 0x000000, roughness: 0.3 });
    const ewYelMat = new THREE.MeshStandardMaterial({ color: 0x78350f, emissive: 0x000000, roughness: 0.3 });
    const ewGrnMat = new THREE.MeshStandardMaterial({ color: 0x064e3b, emissive: 0x000000, roughness: 0.3 });

    signalMatsRef.current = {
      nsRed: nsRedMat,
      nsYellow: nsYelMat,
      nsGreen: nsGrnMat,
      ewRed: ewRedMat,
      ewYellow: ewYelMat,
      ewGreen: ewGrnMat,
    };

    const createSignalGantry = (x: number, z: number, rotY: number, isNS: boolean) => {
      const gantry = new THREE.Group();
      const mastGeo = new THREE.CylinderGeometry(0.24, 0.3, 7.6, 12);
      const mast = new THREE.Mesh(mastGeo, poleMat);
      mast.position.y = 3.8;
      mast.castShadow = true;
      gantry.add(mast);

      const armGeo = new THREE.CylinderGeometry(0.18, 0.18, 6.6, 12);
      const arm = new THREE.Mesh(armGeo, poleMat);
      arm.rotation.z = Math.PI / 2;
      arm.position.set(-3.1, 7.2, 0);
      arm.castShadow = true;
      gantry.add(arm);

      // Signal Head Housing with sun visor
      const headGeo = new THREE.BoxGeometry(0.85, 2.4, 0.55);
      const head = new THREE.Mesh(headGeo, housingMat);
      head.position.set(-5.4, 6.6, 0);
      head.castShadow = true;
      gantry.add(head);

      const lampGeo = new THREE.SphereGeometry(0.28, 16, 16);
      const rMat = isNS ? nsRedMat : ewRedMat;
      const yMat = isNS ? nsYelMat : ewYelMat;
      const gMat = isNS ? nsGrnMat : ewGrnMat;

      const lampR = new THREE.Mesh(lampGeo, rMat);
      lampR.position.set(-5.4, 7.35, 0.28);
      gantry.add(lampR);

      const lampY = new THREE.Mesh(lampGeo, yMat);
      lampY.position.set(-5.4, 6.6, 0.28);
      gantry.add(lampY);

      const lampG = new THREE.Mesh(lampGeo, gMat);
      lampG.position.set(-5.4, 5.85, 0.28);
      gantry.add(lampG);

      gantry.position.set(x, 0, z);
      gantry.rotation.y = rotY;
      scene.add(gantry);
    };

    createSignalGantry(12.8, -13.5, -Math.PI / 2, true);  // North approach
    createSignalGantry(-12.8, 13.5, Math.PI / 2, true);   // South approach
    createSignalGantry(13.5, 12.8, Math.PI, false);       // East approach
    createSignalGantry(-13.5, -12.8, 0, false);           // West approach

    // 11. Procedural High-Fidelity Fallback Mesh Builders (Substantial Dimensions)
    const createFallbackVehicleMesh = (type: 'bus' | 'car' | 'suv', color: number) => {
      const group = new THREE.Group();
      const wheelMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.8 });

      if (type === 'bus') {
        const length = 10.2;
        const busMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.35, metalness: 0.1 });
        const bodyGeo = new THREE.BoxGeometry(3.2, 3.1, length);
        const body = new THREE.Mesh(bodyGeo, busMat);
        body.position.y = 1.9;
        body.castShadow = true;
        group.add(body);

        const winGeo = new THREE.BoxGeometry(3.25, 1.1, length * 0.88);
        const winMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.1 });
        const win = new THREE.Mesh(winGeo, winMat);
        win.position.y = 2.3;
        group.add(win);

        [-1.3, 1.3].forEach((wx) => {
          [-3.2, 3.2].forEach((wz) => {
            const wGeo = new THREE.CylinderGeometry(0.55, 0.55, 0.45, 16);
            const wMesh = new THREE.Mesh(wGeo, wheelMat);
            wMesh.rotation.z = Math.PI / 2;
            wMesh.position.set(wx, 0.55, wz);
            wMesh.name = 'fallback-wheel';
            group.add(wMesh);
          });
        });
      } else {
        const length = type === 'suv' ? 5.2 : 4.8;
        const height = type === 'suv' ? 1.8 : 1.55;
        const carMat = new THREE.MeshStandardMaterial({ color, roughness: 0.3, metalness: 0.25 });

        const lowerGeo = new THREE.BoxGeometry(2.3, 0.85, length);
        const lower = new THREE.Mesh(lowerGeo, carMat);
        lower.position.y = 0.75;
        lower.castShadow = true;
        group.add(lower);

        const cabinGeo = new THREE.BoxGeometry(2.0, height - 0.45, length * 0.55);
        const cabin = new THREE.Mesh(cabinGeo, carMat);
        cabin.position.set(0, 0.75 + (height - 0.45) / 2 + 0.3, -0.2);
        cabin.castShadow = true;
        group.add(cabin);

        const winGeo = new THREE.BoxGeometry(2.05, height * 0.5, length * 0.5);
        const winMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.1 });
        const win = new THREE.Mesh(winGeo, winMat);
        win.position.set(0, 0.8 + height * 0.28, -0.2);
        group.add(win);

        [-1.1, 1.1].forEach((wx) => {
          [-1.5, 1.5].forEach((wz) => {
            const wGeo = new THREE.CylinderGeometry(0.42, 0.42, 0.32, 16);
            const wMesh = new THREE.Mesh(wGeo, wheelMat);
            wMesh.rotation.z = Math.PI / 2;
            wMesh.position.set(wx, 0.42, wz);
            wMesh.name = 'fallback-wheel';
            group.add(wMesh);
          });
        });
      }
      return group;
    };

    // 12. Fleet Definition (Prominent scales, realistic lane offsets)
    const vehicles: VehicleEntity[] = [
      {
        id: 'bus_we',
        name: 'Metro Transit Bus',
        type: 'bus',
        mesh: createFallbackVehicleMesh('bus', 0x0284c7),
        direction: 'W_to_E',
        laneOffset: 3.5,
        length: 11.2,
        targetSpeed: 13.0, // ~47 km/h
        currentSpeed: 13.0,
        pos: -19.0, // Directly visible at West stopline
        state: 'CRUISING',
        wheelNodes: [],
        wheelRadius: 0.47,
        wheelSpinAxis: 'z',
      },
      {
        id: 'car_we_2',
        name: 'NYC Yellow Taxi',
        type: 'car',
        mesh: createFallbackVehicleMesh('car', 0xf59e0b),
        direction: 'W_to_E',
        laneOffset: 7.0,
        length: 4.8,
        targetSpeed: 15.0,
        currentSpeed: 15.0,
        pos: -22.0, // Alongside bus in right lane
        state: 'CRUISING',
        wheelNodes: [],
        wheelRadius: 0.61,
        wheelSpinAxis: 'x',
      },
      {
        id: 'car_sn_1',
        name: 'Pearl White Sedan',
        type: 'car',
        mesh: createFallbackVehicleMesh('car', 0xf8fafc),
        direction: 'S_to_N',
        laneOffset: 3.5,
        length: 4.8,
        targetSpeed: 16.0,
        currentSpeed: 16.0,
        pos: -18.0, // South approach stopline
        state: 'CRUISING',
        wheelNodes: [],
        wheelRadius: 0.61,
        wheelSpinAxis: 'x',
      },
      {
        id: 'car_sn_2',
        name: 'Silver SUV',
        type: 'suv',
        mesh: createFallbackVehicleMesh('suv', 0x94a3b8),
        direction: 'S_to_N',
        laneOffset: 7.0,
        length: 5.0,
        targetSpeed: 15.5,
        currentSpeed: 15.5,
        pos: -28.0,
        state: 'CRUISING',
        wheelNodes: [],
        wheelRadius: 0.64,
        wheelSpinAxis: 'x',
      },
      {
        id: 'car_ns_1',
        name: 'Executive Blue Sedan',
        type: 'car',
        mesh: createFallbackVehicleMesh('car', 0x1d4ed8),
        direction: 'N_to_S',
        laneOffset: -3.5,
        length: 4.8,
        targetSpeed: 15.0,
        currentSpeed: 15.0,
        pos: -18.0, // North approach stopline
        state: 'CRUISING',
        wheelNodes: [],
        wheelRadius: 0.61,
        wheelSpinAxis: 'x',
      },
      {
        id: 'car_ns_2',
        name: 'Charcoal SUV',
        type: 'suv',
        mesh: createFallbackVehicleMesh('suv', 0x334155),
        direction: 'N_to_S',
        laneOffset: -7.0,
        length: 5.0,
        targetSpeed: 14.5,
        currentSpeed: 14.5,
        pos: -29.0,
        state: 'CRUISING',
        wheelNodes: [],
        wheelRadius: 0.64,
        wheelSpinAxis: 'x',
      },
      {
        id: 'car_ew_1',
        name: 'Crimson SUV',
        type: 'suv',
        mesh: createFallbackVehicleMesh('suv', 0xdc2626),
        direction: 'E_to_W',
        laneOffset: -3.5,
        length: 5.0,
        targetSpeed: 14.5,
        currentSpeed: 14.5,
        pos: -18.0, // East approach stopline
        state: 'CRUISING',
        wheelNodes: [],
        wheelRadius: 0.64,
        wheelSpinAxis: 'x',
      },
      {
        id: 'car_ew_2',
        name: 'City Taxi',
        type: 'car',
        mesh: createFallbackVehicleMesh('car', 0xf59e0b),
        direction: 'E_to_W',
        laneOffset: -7.0,
        length: 4.8,
        targetSpeed: 16.0,
        currentSpeed: 16.0,
        pos: -30.0,
        state: 'CRUISING',
        wheelNodes: [],
        wheelRadius: 0.61,
        wheelSpinAxis: 'x',
      },
    ];

    vehicles.forEach((v) => scene.add(v.mesh));
    vehiclesRef.current = vehicles;

    // 13. Preload Color Variant Textures (SRGBColorSpace, flipY=false for exact glTF UV alignment)
    const textureLoader = new THREE.TextureLoader();
    const carTextures: Record<string, THREE.Texture> = {
      pearl_white: textureLoader.load('/models/Textures/colormap_pearl_white.png'),
      blue: textureLoader.load('/models/Textures/colormap_blue.png'),
      charcoal: textureLoader.load('/models/Textures/colormap_charcoal.png'),
      crimson: textureLoader.load('/models/Textures/colormap_crimson.png'),
      silver: textureLoader.load('/models/Textures/colormap_silver.png'),
      amber: textureLoader.load('/models/Textures/colormap_amber.png'),
    };

    Object.values(carTextures).forEach((tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.flipY = false;
    });

    const vehicleColorVariants: Record<string, string> = {
      car_sn_1: 'pearl_white',
      car_sn_2: 'silver',
      car_ns_1: 'blue',
      car_ns_2: 'charcoal',
      car_ew_1: 'crimson',
      car_ew_2: 'amber',
      car_we_2: 'amber',
    };

    // 14. Asynchronous GLTF Vehicle Asset Loading with Multiple Authentic Models
    const gltfLoader = new GLTFLoader();

    const cloneGLTF = (gltfScene: THREE.Group): THREE.Group => {
      const clone = gltfScene.clone(true);
      clone.traverse((node) => {
        if ((node as THREE.Mesh).isMesh) {
          const mesh = node as THREE.Mesh;
          mesh.castShadow = true;
          mesh.receiveShadow = true;
          if (Array.isArray(mesh.material)) {
            mesh.material = mesh.material.map((m) => m.clone());
          } else if (mesh.material) {
            mesh.material = mesh.material.clone();
          }
        }
      });
      return clone;
    };

    // Store loaded templates
    const templates: {
      sedan?: THREE.Group;
      suv?: THREE.Group;
      taxi?: THREE.Group;
    } = {};

    const applyCarModel = (v: VehicleEntity, template: THREE.Group, scale: number) => {
      const carModel = cloneGLTF(template);
      carModel.scale.set(scale, scale, scale);

      const variantName = vehicleColorVariants[v.id] || 'silver';
      const assignedTex = carTextures[variantName];

      const wheels: THREE.Object3D[] = [];
      carModel.traverse((child) => {
        if (child.name.toLowerCase().includes('wheel')) {
          wheels.push(child);
        }
        if ((child as THREE.Mesh).isMesh) {
          const m = child as THREE.Mesh;
          m.castShadow = true;
          m.receiveShadow = true;
          if (m.material && !Array.isArray(m.material)) {
            const std = m.material.clone() as THREE.MeshStandardMaterial;
            std.roughness = 0.35;
            std.metalness = 0.20;
            if (assignedTex) {
              std.map = assignedTex;
              std.needsUpdate = true;
            }
            m.material = std;
          }
        }
      });

      scene.remove(v.mesh);
      v.mesh = carModel;
      v.wheelNodes = wheels;
      v.wheelRadius = 0.30 * scale; // 0.30 is unscaled wheel radius
      v.wheelSpinAxis = 'x';
      scene.add(carModel);
    };

    // Load Sedan Model (Kenney CC0)
    gltfLoader.load(
      '/models/sedan.glb',
      (gltf) => {
        templates.sedan = gltf.scene;
        vehiclesRef.current.forEach((v) => {
          if (v.id === 'car_sn_1' || v.id === 'car_ns_1' || v.id === 'car_we_2') {
            applyCarModel(v, gltf.scene, 2.05);
          }
        });
        setAssetsLoaded(true);
      },
      undefined,
      (err) => console.warn('[ThreeIntersection] Could not load /models/sedan.glb', err)
    );

    // Load SUV Model (Kenney CC0)
    gltfLoader.load(
      '/models/suv.glb',
      (gltf) => {
        templates.suv = gltf.scene;
        vehiclesRef.current.forEach((v) => {
          if (v.id === 'car_sn_2' || v.id === 'car_ns_2' || v.id === 'car_ew_1') {
            applyCarModel(v, gltf.scene, 2.15);
          }
        });
      },
      undefined,
      (err) => console.warn('[ThreeIntersection] Could not load /models/suv.glb', err)
    );

    // Load Taxi Model (Kenney CC0 - NYC Checkered Yellow Cab)
    gltfLoader.load(
      '/models/taxi.glb',
      (gltf) => {
        templates.taxi = gltf.scene;
        vehiclesRef.current.forEach((v) => {
          if (v.id === 'car_ew_2') {
            applyCarModel(v, gltf.scene, 2.05);
          }
        });
      },
      undefined,
      (err) => console.warn('[ThreeIntersection] Could not load /models/taxi.glb', err)
    );

    // Load Bus Model (Quaternius CC0 with Realistic Multi-PBR Material Shading & Fixed Pivot)
    gltfLoader.load(
      '/models/bus.glb',
      (gltf) => {
        console.log('[ThreeIntersection] bus.glb loaded successfully');
        const busScene = gltf.scene;

        vehiclesRef.current.forEach((v) => {
          if (v.type === 'bus') {
            const busModel = new THREE.Group();
            const busSub = cloneGLTF(busScene);

            // Quaternius bus center X ~1.765, facing -X. Center pivot and rotate 90° so it faces +Z
            busSub.position.set(-1.765, 0.95, 0);
            busSub.rotation.y = Math.PI / 2;

            // Scale 2.85x brings bus length to ~11.6m with commanding realism
            const busScale = 2.85;
            busSub.scale.set(busScale, busScale, busScale);

            // High-fidelity transit livery materials preserving original material instances
            const configureBusMaterial = (mat: THREE.Material): THREE.Material => {
              const m = (mat as THREE.MeshStandardMaterial).clone();
              const n = (m.name || '').toLowerCase();

              if (n.includes('window')) {
                // Sleek tinted automotive glass with specular reflection
                m.color.setHex(0x0f172a);
                m.roughness = 0.08;
                m.metalness = 0.85;
                m.transparent = true;
                m.opacity = 0.88;
              } else if (n.includes('top')) {
                // Vibrant municipal transit blue livery (Metro Blue)
                m.color.setHex(0x0284c7);
                m.roughness = 0.28;
                m.metalness = 0.25;
              } else if (n.includes('bottom')) {
                // Deep municipal transit blue chassis skirt
                m.color.setHex(0x0369a1);
                m.roughness = 0.32;
                m.metalness = 0.25;
              } else if (n.includes('bumper')) {
                // Heavy-duty charcoal safety bumpers
                m.color.setHex(0x1e293b);
                m.roughness = 0.75;
                m.metalness = 0.2;
              } else if (n.includes('light')) {
                // High-intensity headlights with warm LED emissive glow
                m.color.setHex(0xffffff);
                m.emissive.setHex(0xfef08a);
                m.emissiveIntensity = 2.0;
                m.roughness = 0.15;
              } else if (n.includes('detail')) {
                // Front grille and rearview mirrors
                m.color.setHex(0x334155);
                m.roughness = 0.4;
                m.metalness = 0.6;
              } else {
                // Tires / Wheel rubber
                m.color.setHex(0x111827);
                m.roughness = 0.85;
                m.metalness = 0.1;
              }
              m.needsUpdate = true;
              return m;
            };

            const wheels: THREE.Object3D[] = [];

            busSub.traverse((child) => {
              if ((child as THREE.Mesh).isMesh) {
                const mesh = child as THREE.Mesh;
                mesh.castShadow = true;
                mesh.receiveShadow = true;

                // Apply materials
                if (Array.isArray(mesh.material)) {
                  mesh.material = mesh.material.map(configureBusMaterial);
                } else if (mesh.material) {
                  mesh.material = configureBusMaterial(mesh.material);
                }

                // Inspect and log wheel hierarchy, center geometry around axle pivot
                if (mesh.name.toLowerCase().includes('wheel')) {
                  mesh.geometry = mesh.geometry.clone();
                  mesh.geometry.computeBoundingBox();
                  const box = mesh.geometry.boundingBox!;
                  const center = new THREE.Vector3();
                  box.getCenter(center);

                  console.log(`[BusWheel Hierarchy Inspection] Node: '${mesh.name}'`, {
                    parent: mesh.parent?.name || 'busSub',
                    localTransform: {
                      position: mesh.position.toArray(),
                      rotation: mesh.rotation.toArray(),
                      scale: mesh.scale.toArray(),
                    },
                    boundingBox: {
                      min: box.min.toArray(),
                      max: box.max.toArray(),
                    },
                    axleCentroid: center.toArray(),
                  });

                  // Centering geometry eliminates orbiting around (0,0,0)
                  mesh.geometry.translate(-center.x, -center.y, -center.z);
                  mesh.position.copy(center);

                  wheels.push(mesh);
                }
              }
            });

            busModel.add(busSub);

            scene.remove(v.mesh);
            v.mesh = busModel;
            v.wheelNodes = wheels;
            v.wheelRadius = 0.1645 * busScale; // ~0.47m
            v.wheelSpinAxis = 'z';
            scene.add(busModel);
          }
        });
      },
      undefined,
      (err) => console.warn('[ThreeIntersection] Fallback active: could not load /models/bus.glb', err)
    );

    // 14. Interactive Mouse Orbit Controls
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };
    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const dx = e.clientX - prevMouseX;
      const dy = e.clientY - prevMouseY;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;

      spherical.theta -= dx * 0.008;
      spherical.phi = Math.max(0.12, Math.min(Math.PI / 2.08, spherical.phi - dy * 0.008));
      updateCameraPos();
    };
    const onMouseUp = () => {
      isDragging = false;
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      spherical.radius = Math.max(26, Math.min(85, spherical.radius + e.deltaY * 0.05));
      updateCameraPos();
    };

    container.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    container.addEventListener('wheel', onWheel, { passive: false });

    // 15. Delta-Time Physical Simulation Loop
    const clock = new THREE.Clock();
    let animId: number;
    let lastDiagPush = 0;
    let frameCount = 0;
    let lastFpsCalc = performance.now();
    let currentFps = 60;
    const startTime = performance.now();

    const animate = () => {
      animId = requestAnimationFrame(animate);

      const rawDt = clock.getDelta();
      const dt = Math.max(0.001, Math.min(0.1, rawDt));

      const now = performance.now();
      const elapsedSeconds = (now - startTime) / 1000.0;
      const { currentStep: liveStep, isSimulating: liveSimulating } = propsRef.current;

      // Track measured FPS
      frameCount++;
      if (now - lastFpsCalc >= 1000) {
        currentFps = Math.round((frameCount * 1000) / (now - lastFpsCalc));
        frameCount = 0;
        lastFpsCalc = now;
      }

      // Determine Phasing State
      let phase = 0;
      let isYellow = false;
      let phaseLabel = '';
      let mode: 'AUTONOMOUS_CYCLE' | 'TRACI_REPLAY' = 'AUTONOMOUS_CYCLE';

      if (liveSimulating && liveStep) {
        mode = 'TRACI_REPLAY';
        phase = liveStep.active_green_phase;
        isYellow = liveStep.clearance_executed;
        phaseLabel = isYellow
          ? `SUMO Clearance (Step ${liveStep.step}, ${liveStep.simulation_time.toFixed(1)}s)`
          : `SUMO Phase ${phase}: ${phase === 0 ? 'North-South' : 'East-West'} Green`;
      } else {
        // Autonomous Demo Phasing Cycle (28.0s: 11s NS Green, 3s Yellow, 11s EW Green, 3s Yellow)
        mode = 'AUTONOMOUS_CYCLE';
        const cyclePeriod = 28.0;
        const cycleT = elapsedSeconds % cyclePeriod;

        if (cycleT < 11.0) {
          phase = 0;
          isYellow = false;
          phaseLabel = `Phase 0: North-South Green (${(11.0 - cycleT).toFixed(1)}s)`;
        } else if (cycleT < 14.0) {
          phase = 0;
          isYellow = true;
          phaseLabel = `Yellow Clearance NS (${(14.0 - cycleT).toFixed(1)}s)`;
        } else if (cycleT < 25.0) {
          phase = 2;
          isYellow = false;
          phaseLabel = `Phase 2: East-West Green (${(25.0 - cycleT).toFixed(1)}s)`;
        } else {
          phase = 2;
          isYellow = true;
          phaseLabel = `Yellow Clearance EW (${(28.0 - cycleT).toFixed(1)}s)`;
        }
      }

      // Signal states
      const nsGreen = !isYellow && phase === 0;
      const nsYellow = isYellow && (phase === 0 || phase === 1);
      const nsRed = !nsGreen && !nsYellow;

      const ewGreen = !isYellow && phase === 2;
      const ewYellow = isYellow && (phase === 2 || phase === 3);
      const ewRed = !ewGreen && !ewYellow;

      // Update 3D Signal Lamps with glowing emissive intensity
      const mats = signalMatsRef.current;
      if (mats) {
        if (nsGreen) {
          mats.nsGreen.emissive.setHex(0x10b981);
          mats.nsYellow.emissive.setHex(0x000000);
          mats.nsRed.emissive.setHex(0x000000);
        } else if (nsYellow) {
          mats.nsGreen.emissive.setHex(0x000000);
          mats.nsYellow.emissive.setHex(0xf59e0b);
          mats.nsRed.emissive.setHex(0x000000);
        } else {
          mats.nsGreen.emissive.setHex(0x000000);
          mats.nsYellow.emissive.setHex(0x000000);
          mats.nsRed.emissive.setHex(0xef4444);
        }

        if (ewGreen) {
          mats.ewGreen.emissive.setHex(0x10b981);
          mats.ewYellow.emissive.setHex(0x000000);
          mats.ewRed.emissive.setHex(0x000000);
        } else if (ewYellow) {
          mats.ewGreen.emissive.setHex(0x000000);
          mats.ewYellow.emissive.setHex(0xf59e0b);
          mats.ewRed.emissive.setHex(0x000000);
        } else {
          mats.ewGreen.emissive.setHex(0x000000);
          mats.ewYellow.emissive.setHex(0x000000);
          mats.ewRed.emissive.setHex(0xef4444);
        }
      }

      // Vehicle Kinematics & Wheel Rotation
      const currentVehicles = vehiclesRef.current;
      const stopLine = -15.5;

      currentVehicles.forEach((v) => {
        const isNS = v.direction === 'N_to_S' || v.direction === 'S_to_N';
        const hasYellow = isNS ? nsYellow : ewYellow;
        const hasRed = isNS ? nsRed : ewRed;

        // Find leader in same lane
        let leadVehicle: VehicleEntity | null = null;
        let leadDist = 999;
        for (const other of currentVehicles) {
          if (other.id !== v.id && other.direction === v.direction && other.laneOffset === v.laneOffset) {
            const d = other.pos - (other.length / 2) - (v.pos + v.length / 2);
            if (d > -1.0 && d < leadDist) {
              leadDist = d;
              leadVehicle = other;
            }
          }
        }

        let targetStopPos = 999;
        let stopReason: 'NONE' | 'RED' | 'LEADER' = 'NONE';

        if ((hasRed || hasYellow) && v.pos < stopLine) {
          targetStopPos = stopLine - (v.length / 2);
          stopReason = 'RED';
        }

        if (leadVehicle !== null && leadDist < 15.0) {
          const leader: VehicleEntity = leadVehicle;
          const leaderFollowPos = leader.pos - (leader.length / 2) - (v.length / 2) - 4.0;
          if (leaderFollowPos < targetStopPos) {
            targetStopPos = leaderFollowPos;
            stopReason = 'LEADER';
          }
        }

        const distToStop = targetStopPos - v.pos;

        // Kinematics acceleration & braking
        if (stopReason !== 'NONE' && distToStop < 30.0) {
          if (distToStop <= 0.3) {
            v.currentSpeed = 0.0;
            v.pos = Math.min(v.pos, targetStopPos);
            v.state = stopReason === 'RED' ? 'STOPPED_SIGNAL' : 'QUEUED';
          } else {
            const decelTarget = Math.max(0.5, distToStop * 1.8);
            v.currentSpeed = Math.max(0.0, Math.min(v.currentSpeed, decelTarget));
            v.pos += v.currentSpeed * dt;
            v.state = 'DECELERATING';
          }
        } else {
          v.currentSpeed = Math.min(v.targetSpeed, v.currentSpeed + 3.0 * dt);
          v.pos += v.currentSpeed * dt;
          v.state = 'CRUISING';
        }

        // Wheel Rotation Animation based on actual ground speed
        if (v.wheelNodes.length > 0 && v.currentSpeed > 0.01) {
          const spinDelta = (v.currentSpeed * dt) / v.wheelRadius;
          v.wheelNodes.forEach((w) => {
            if (v.wheelSpinAxis === 'z') {
              w.rotation.z += spinDelta;
            } else {
              w.rotation.x += spinDelta;
            }
          });
        }

        // Recycle Vehicle when exiting view
        if (v.pos > 60.0) {
          v.pos = -55.0 - Math.random() * 12.0;
          v.currentSpeed = v.targetSpeed * 0.85;
          v.state = 'CRUISING';
        }

        // Coordinate & Heading Transformations
        if (v.direction === 'S_to_N') {
          v.mesh.position.set(v.laneOffset, 0, -v.pos);
          v.mesh.rotation.y = Math.PI;
        } else if (v.direction === 'N_to_S') {
          v.mesh.position.set(v.laneOffset, 0, v.pos);
          v.mesh.rotation.y = 0;
        } else if (v.direction === 'W_to_E') {
          v.mesh.position.set(v.pos, 0, -v.laneOffset);
          v.mesh.rotation.y = Math.PI / 2;
        } else if (v.direction === 'E_to_W') {
          v.mesh.position.set(-v.pos, 0, -v.laneOffset);
          v.mesh.rotation.y = -Math.PI / 2;
        }
      });

      // Update Diagnostics HUD state
      if (now - lastDiagPush > 100) {
        lastDiagPush = now;
        setDiagInfo({
          animTime: elapsedSeconds,
          fps: currentFps,
          deltaMs: Math.round(dt * 1000 * 10) / 10,
          phaseLabel,
          nsState: nsGreen ? 'GREEN' : nsYellow ? 'YELLOW' : 'RED',
          ewState: ewGreen ? 'GREEN' : ewYellow ? 'YELLOW' : 'RED',
          mode,
          vehicles: currentVehicles.map((cv) => ({
            id: cv.id,
            name: cv.name,
            pos: Math.round(cv.pos * 10) / 10,
            speed: Math.round(cv.currentSpeed * 10) / 10,
            state: cv.state,
          })),
        });
      }

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight || 500;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      container.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      container.removeEventListener('wheel', onWheel);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
    };
  }, []);

  const setPreset = (view: 'cinematic' | 'top' | 'driver') => {
    setCameraView(view);
    const camera = cameraRef.current;
    if (!camera) return;

    if (view === 'cinematic') {
      camera.position.set(28, 22, 28);
      camera.lookAt(0, 0.8, 0);
    } else if (view === 'top') {
      camera.position.set(0.1, 60, 0.1);
      camera.lookAt(0, 0, 0);
    } else if (view === 'driver') {
      camera.position.set(16, 6.5, 18);
      camera.lookAt(0, 1.2, 0);
    }
  };

  return (
    <div className="card-premium" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header Bar */}
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 dot-pulse" style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
          <h3 className="card-title" style={{ margin: 0 }}>
            3D Urban Intersection Simulation (TLS &quot;C&quot;)
          </h3>
          <span className="badge badge-amber font-mono" style={{ fontSize: '10px' }}>8 Approaches · TraCI</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isSimulating ? (
            <span className="badge badge-emerald font-mono">
              <Activity style={{ width: '12px', height: '12px', animation: 'spin 1s linear infinite' }} /> SUMO TraCI
            </span>
          ) : (
            <span className="badge badge-blue font-mono" style={{ fontSize: '11px' }}>
              Kinematic Sim (28s Cycle)
            </span>
          )}
          <span className="badge badge-neutral font-mono" style={{ fontSize: '11px' }}>
            Daylight · Soft Shadows
          </span>
        </div>
      </div>

      {/* 3D WebGL Canvas Container with Strict Containment */}
      <div style={{ position: 'relative', width: '100%', height: '480px', overflow: 'hidden', background: '#f8fafc' }}>
        <div ref={mountRef} style={{ width: '100%', height: '100%' }} />

        {/* Top Floating Controls — Fully Contained Inside Canvas */}
        <div style={{
          position: 'absolute',
          top: '12px',
          left: '14px',
          right: '14px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pointerEvents: 'none',
          zIndex: 20
        }}>
          {/* Active Phase Pill */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.94)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(226, 232, 240, 0.9)',
            borderRadius: '8px',
            padding: '6px 12px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            pointerEvents: 'auto'
          }}>
            <span
              style={{
                width: '9px',
                height: '9px',
                borderRadius: '50%',
                background:
                  diagInfo.nsState === 'GREEN' || diagInfo.ewState === 'GREEN'
                    ? '#10b981'
                    : diagInfo.nsState === 'YELLOW' || diagInfo.ewState === 'YELLOW'
                    ? '#f59e0b'
                    : '#ef4444'
              }}
              className="dot-pulse"
            />
            <div>
              <span style={{ fontSize: '10px', color: '#64748b', display: 'block', fontWeight: 600 }}>SIGNAL PHASE</span>
              <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: '#0f172a' }}>
                {diagInfo.phaseLabel}
              </strong>
            </div>
          </div>

          {/* Camera View Switcher & Diagnostics Button */}
          <div style={{
            background: 'rgba(255, 255, 255, 0.94)',
            backdropFilter: 'blur(8px)',
            border: '1px solid rgba(226, 232, 240, 0.9)',
            borderRadius: '8px',
            padding: '4px',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
            display: 'flex',
            gap: '3px',
            pointerEvents: 'auto'
          }}>
            <button
              onClick={() => setPreset('cinematic')}
              className={`pill-btn ${cameraView === 'cinematic' ? 'pill-btn-active' : ''}`}
              style={{ padding: '4px 10px', fontSize: '11px' }}
            >
              <Eye style={{ width: '12px', height: '12px', display: 'inline', marginRight: '4px' }} /> Cinematic 3/4
            </button>
            <button
              onClick={() => setPreset('top')}
              className={`pill-btn ${cameraView === 'top' ? 'pill-btn-active' : ''}`}
              style={{ padding: '4px 10px', fontSize: '11px' }}
            >
              <Camera style={{ width: '12px', height: '12px', display: 'inline', marginRight: '4px' }} /> Aerial
            </button>
            <button
              onClick={() => setPreset('driver')}
              className={`pill-btn ${cameraView === 'driver' ? 'pill-btn-active' : ''}`}
              style={{ padding: '4px 10px', fontSize: '11px' }}
            >
              <Compass style={{ width: '12px', height: '12px', display: 'inline', marginRight: '4px' }} /> Street
            </button>
            <button
              onClick={() => setShowDiagnostics((prev) => !prev)}
              className={`pill-btn ${showDiagnostics ? 'pill-btn-active-amber' : ''}`}
              style={{ padding: '4px 10px', fontSize: '11px' }}
              title="Toggle Movement Diagnostics HUD"
            >
              <Terminal style={{ width: '12px', height: '12px', display: 'inline', marginRight: '4px' }} />
              HUD {showDiagnostics ? <ChevronUp style={{ width: '12px', height: '12px', display: 'inline' }} /> : <ChevronDown style={{ width: '12px', height: '12px', display: 'inline' }} />}
            </button>
          </div>
        </div>

        {/* Scientific Limitation Disclosure Banner */}
        <div
          style={{
            position: 'absolute',
            bottom: '12px',
            left: '14px',
            maxWidth: '430px',
            backgroundColor: 'rgba(15, 23, 42, 0.78)',
            backdropFilter: 'blur(6px)',
            color: '#cbd5e1',
            borderRadius: '6px',
            padding: '6px 10px',
            fontSize: '10px',
            lineHeight: '1.4',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            zIndex: 10,
          }}
        >
          <Info style={{ width: '13px', height: '13px', color: '#38bdf8', flexShrink: 0 }} />
          <span>
            {isSimulating
              ? 'Signal lamps driven authentically by SUMO TraCI. Trajectories illustrate dynamic flow physics (vehicle coords are not streamed by SUMO step API).'
              : 'Illustrative client-side simulation with autonomous 28s cycle demonstrating vehicle stopping, queueing, and discharge dynamics.'}
          </span>
        </div>

        {/* Diagnostics HUD Overlay (Contained neatly inside canvas on top right) */}
        {showDiagnostics && (
          <div
            style={{
              position: 'absolute',
              top: '56px',
              right: '14px',
              width: '300px',
              backgroundColor: 'rgba(15, 23, 42, 0.92)',
              backdropFilter: 'blur(8px)',
              color: '#f8fafc',
              borderRadius: '8px',
              padding: '10px 12px',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.35)',
              zIndex: 35,
              maxHeight: '380px',
              overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255, 255, 255, 0.1)', paddingBottom: '6px', marginBottom: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#38bdf8', fontWeight: 700 }}>
                <Terminal style={{ width: '12px', height: '12px' }} />
                <span>KINEMATICS HUD</span>
              </div>
              <span style={{ color: '#94a3b8', fontSize: '10px' }}>{diagInfo.fps} FPS · {diagInfo.deltaMs}ms</span>
            </div>

            {/* Signal Heads Telemetry */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginBottom: '8px' }}>
              <div style={{ background: 'rgba(255,255,255,0.06)', padding: '5px 7px', borderRadius: '4px' }}>
                <div style={{ color: '#94a3b8', fontSize: '9px' }}>NORTH-SOUTH</div>
                <div style={{
                  fontWeight: 800,
                  fontSize: '11px',
                  color: diagInfo.nsState === 'GREEN' ? '#34d399' : diagInfo.nsState === 'YELLOW' ? '#fbbf24' : '#f87171'
                }}>
                  {diagInfo.nsState}
                </div>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.06)', padding: '5px 7px', borderRadius: '4px' }}>
                <div style={{ color: '#94a3b8', fontSize: '9px' }}>EAST-WEST</div>
                <div style={{
                  fontWeight: 800,
                  fontSize: '11px',
                  color: diagInfo.ewState === 'GREEN' ? '#34d399' : diagInfo.ewState === 'YELLOW' ? '#fbbf24' : '#f87171'
                }}>
                  {diagInfo.ewState}
                </div>
              </div>
            </div>

            <div style={{ marginBottom: '8px', background: 'rgba(255,255,255,0.04)', padding: '5px 7px', borderRadius: '4px', fontSize: '10px' }}>
              <div style={{ color: '#94a3b8', fontSize: '9px' }}>ACTIVE ASSETS</div>
              <div style={{ color: '#38bdf8' }}>{assetsLoaded ? 'Kenney/Quaternius GLB' : 'Procedural Fallback'}</div>
            </div>

            {/* Vehicle Kinematics Table */}
            <div style={{ color: '#94a3b8', fontSize: '9px', marginBottom: '4px' }}>VEHICLE DYNAMICS (8 UNITS)</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              {diagInfo.vehicles.map((vh) => (
                <div
                  key={vh.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '3px 5px',
                    borderRadius: '3px',
                    background: 'rgba(255, 255, 255, 0.03)',
                    fontSize: '10px',
                  }}
                >
                  <span style={{ color: '#e2e8f0', maxWidth: '110px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {vh.name}
                  </span>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <span style={{ color: '#38bdf8' }}>{vh.speed.toFixed(1)} m/s</span>
                    <span
                      style={{
                        padding: '1px 3px',
                        borderRadius: '2px',
                        fontSize: '9px',
                        fontWeight: 600,
                        backgroundColor:
                          vh.state === 'CRUISING'
                            ? 'rgba(16, 185, 129, 0.2)'
                            : vh.state === 'DECELERATING'
                            ? 'rgba(245, 158, 11, 0.2)'
                            : 'rgba(239, 68, 68, 0.2)',
                        color:
                          vh.state === 'CRUISING'
                            ? '#34d399'
                            : vh.state === 'DECELERATING'
                            ? '#fbbf24'
                            : '#f87171',
                      }}
                    >
                      {vh.state}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Card Footer: Clean, Non-Overlapping Research Status Bar */}
      <div className="card-footer" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
        gap: '12px',
        padding: '12px 18px',
        background: '#fafbfc'
      }}>
        <div>
          <span style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, display: 'block' }}>
            Signal Phasing
          </span>
          <span style={{
            fontSize: '12px',
            fontFamily: 'var(--font-mono)',
            fontWeight: 700,
            color: diagInfo.nsState === 'GREEN' || diagInfo.ewState === 'GREEN' ? '#059669' : diagInfo.nsState === 'YELLOW' || diagInfo.ewState === 'YELLOW' ? '#d97706' : '#dc2626'
          }}>
            {diagInfo.phaseLabel}
          </span>
        </div>
        <div>
          <span style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, display: 'block' }}>
            Simulation Clock
          </span>
          <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)' }}>
            {diagInfo.animTime.toFixed(1)}s
          </span>
        </div>
        <div>
          <span style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, display: 'block' }}>
            Engine Framerate
          </span>
          <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#059669' }}>
            {diagInfo.fps} FPS · {diagInfo.deltaMs}ms
          </span>
        </div>
        <div>
          <span style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, display: 'block' }}>
            Queue (NS / EW)
          </span>
          <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)' }}>
            {queueNS.toFixed(1)} / {queueEW.toFixed(1)} veh
          </span>
        </div>
      </div>
    </div>
  );
};
