"""Optional fully-local neural text-to-3D via OpenAI's Shap-E.

Heavy optional dependencies (NOT installed by default):
    pip install torch
    pip install git+https://github.com/openai/shap-e

First run downloads ~1 GB of model weights. A GPU is strongly recommended;
CPU generation takes several minutes per model.
"""
import tempfile


class ShapEMissing(RuntimeError):
    pass


def text_to_3d(prompt: str, guidance_scale: float = 15.0, steps: int = 64):
    try:
        import torch
        from shap_e.diffusion.sample import sample_latents
        from shap_e.diffusion.gaussian_diffusion import diffusion_from_config
        from shap_e.models.download import load_model, load_config
        from shap_e.util.notebooks import decode_latent_mesh
    except ImportError as e:
        raise ShapEMissing(
            "Shap-E is not installed. Run: pip install torch && "
            "pip install git+https://github.com/openai/shap-e "
            "inside backend/.venv, then restart the server."
        ) from e

    import trimesh

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    xm = load_model("transmitter", device=device)
    model = load_model("text300M", device=device)
    diffusion = diffusion_from_config(load_config("diffusion"))

    latents = sample_latents(
        batch_size=1,
        model=model,
        diffusion=diffusion,
        guidance_scale=guidance_scale,
        model_kwargs=dict(texts=[prompt]),
        progress=False,
        clip_denoised=True,
        use_fp16=torch.cuda.is_available(),
        use_karras=True,
        karras_steps=steps,
        sigma_min=1e-3,
        sigma_max=160,
        s_churn=0,
    )
    tri_mesh = decode_latent_mesh(xm, latents[0]).tri_mesh()
    with tempfile.NamedTemporaryFile(suffix=".ply", delete=False) as f:
        tri_mesh.write_ply(f)
        path = f.name
    return trimesh.load(path)
