# Fine-cell foam mat textures

Original, procedurally authored seamless maps for the dark foam work mat.
No photographs or third-party texture assets are included.

- `foam_basecolor.png`: sRGB albedo with subtle, irregular compression mottling and fine pore variation.
- `foam_normal.png`: tangent-space normal map; read as linear data. Its shallow relief affects shading only.

Both maps are 2048 × 2048. One UV repeat spans the existing mat surface
(approximately 457 × 305 mm). `mat-thick-collision.usda` sets the roughness,
specular strength, and normal strength. Geometry, thickness, friction,
collision shape, and contact behavior come from the unchanged source asset.

These are appearance approximations checked against camera images, not a
measured optical or mechanical model of the foam.
