```plain
POST /assets
        │
        ▼
    Asset PENDING
        │
        │
POST /assets/{asset_id}/uploads
        │
        ├── создаётся upload_id
        ├── строится storage_key
        ├── выдаётся presigned PUT URL
        └── запускается Temporal Workflow
                │
                │ WAITING_FOR_UPLOAD
                │
                ▼
            PUT → S3
                │
                ▼
POST /assets/{asset_id}/uploads/{upload_id}/complete
                │
                └── signal Workflow
                        │
                        ▼
                  inspect file
                        │
                  determine type
                        │
                 extract metadata
                        │
                create AssetVersion
                        │
              create derivatives
                        │
                  finalize Asset
                        │
                        ▼
                  Asset READY
                  current_version → N
```


```plain
POST /assets
    ↓
Asset(PENDING)
    ↓
POST /assets/{id}/upload
    ↓
S3 upload
    ↓
start workflow
    ↓
Workflow
    ├── validate file
    ├── extract metadata
    ├── calculate checksum
    ├── determine type
    ├── create AssetVersion
    ├── generate thumbnail
    ├── generate preview
    ├── generate watermark
    └── finalize Asset
    ↓
Asset(READY)
Version(READY)
current_version = version
```