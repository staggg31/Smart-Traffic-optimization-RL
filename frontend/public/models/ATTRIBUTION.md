# 3D Asset Attribution and License Record

This project includes lightweight, optimized 3D vehicle assets for the real-time WebGL urban intersection simulation. All included 3D assets are licensed under **Creative Commons Zero 1.0 Universal (Public Domain)**.

---

### 1. Sedan (`sedan.glb`)
* **Asset Name:** `sedan.glb` (Car Kit 3.1)
* **Creator / Author:** Kenney ([Kenney.nl](https://kenney.nl))
* **Source:** Kenney Car Kit v3.1 ([https://kenney.nl/assets/car-kit](https://kenney.nl/assets/car-kit) / [OpenGameArt](https://opengameart.org/content/car-kit))
* **License:** Creative Commons Zero 1.0 Universal (CC0 - Public Domain)
  * [https://creativecommons.org/publicdomain/zero/1.0/](https://creativecommons.org/publicdomain/zero/1.0/)
* **File Format & Size:** Binary glTF (`.glb`), **172 KB**
* **Mesh & Node Hierarchy:**
  * Root node
  * `body`: Sedan chassis, roof, windshield, cabin, front/rear bumpers
  * `wheel-front-right`: Dedicated steerable/rotatable wheel node
  * `wheel-front-left`: Dedicated steerable/rotatable wheel node
  * `wheel-back-right`: Dedicated rotatable wheel node
  * `wheel-back-left`: Dedicated rotatable wheel node
* **Bounding Dimensions:** Width 1.50m × Height 1.15m × Length 2.55m
* **Default Orientation:** Forward heading aligned to `+Z`

---

### 2. City Transit Bus (`bus.glb`)
* **Asset Name:** `bus.glb` (LowPoly Public Transport)
* **Creator / Author:** Quaternius ([Quaternius.com](https://quaternius.com/packs/cars.html))
* **Source:** Quaternius LowPoly Public Transport ([OpenGameArt](https://opengameart.org/content/lowpoly-public-transport))
* **License:** Creative Commons Zero 1.0 Universal (CC0 - Public Domain)
  * [https://creativecommons.org/publicdomain/zero/1.0/](https://creativecommons.org/publicdomain/zero/1.0/)
* **Conversion:** Converted from raw Quaternius `Bus.obj` via `obj2gltf` into an ultra-low-footprint binary `.glb`.
* **File Format & Size:** Binary glTF (`.glb`), **79 KB**
* **Mesh & Node Hierarchy:**
  * `Bus_Cube.001`: Bus passenger coach, windows, doors, roof, front grill
  * `FrontWheels_Cylinder.006`: Dual front axle assembly with independent wheel rotation
  * `BackWheels_Cylinder.007`: Dual rear axle assembly with independent wheel rotation
* **Materials:** `Material` (body color), `Windows`, `Details`, `Bumper`, `Lights`, `Top`, `Bottom`
* **Bounding Dimensions:** Width 1.74m × Height 1.68m × Length 4.09m
* **Orientation Correction:** Originally modeled along X-axis; normalized with a +90° yaw transform and pivot centering in Three.js loader.
