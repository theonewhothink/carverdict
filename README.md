# CarVerdict

True car ownership costs computed from public data - NHTSA complaints and recalls, EPA fuel economy - re-priced automatically for the visitor's country. Plus a catalogue of 15,212 car models across 1,162 marques with 11,972 freely-licensed photographs.

Live: https://carsite.adir-073.workers.dev

Build order matters (gen_site.py clears site/):

    pip install pillow
        python scripts/build_models.py --plan
            python scripts/gen_site.py
                python scripts/build_models.py
                    python scripts/build_library.py
                        python scripts/build_engage.py
                            python scripts/localize.py

                            CI (.github/workflows/build-deploy.yml) runs this nightly and on every push, then deploys to Cloudflare Workers.
                            
