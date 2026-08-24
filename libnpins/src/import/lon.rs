//! Convert+Import Lon files

use anyhow::Context;
use serde::{Deserialize, Serialize};
use std::convert::TryFrom;

use crate::{Frozen, GenericHash, Pin, git, urlpin};

impl TryFrom<Source> for Pin {
    type Error = anyhow::Error;

    fn try_from(lon: Source) -> anyhow::Result<Self> {
        Ok(match lon {
            Source::Git(lon) => Pin::Git {
                input: git::GitPin::new(
                    git::Repository::git(lon.url.parse().context("Invalid git repository URL")?),
                    lon.branch,
                    lon.submodules,
                ),
                version: Some(git::GitRevision::new(lon.revision)?),
                hashes: Some(git::OptionalUrlHashes {
                    url: None,
                    hash: lon.hash,
                }),
                frozen: Frozen(lon.frozen),
            },
            Source::GitHub(lon) => Pin::Git {
                input: git::GitPin::new(
                    git::Repository::github(lon.owner, lon.repo),
                    lon.branch,
                    false,
                ),
                version: Some(git::GitRevision::new(lon.revision)?),
                hashes: Some(git::OptionalUrlHashes {
                    url: match lon.fetch_type {
                        FetchType::Tarball => Some(lon.url.parse().context("Invalid tarball URL")?),
                        FetchType::Git => None,
                    },
                    hash: lon.hash,
                }),
                frozen: Frozen(lon.frozen),
            },
            Source::Tarball(lon) => {
                let url: url::Url = lon.url.parse().context("Invalid tarball URL")?;
                let hashes = Some(GenericHash { hash: lon.hash });
                match lon.origin {
                    Some(origin) => Pin::MutableUrl {
                        input: urlpin::MutableUrlPin {
                            update_url: origin.parse().context("Invalid tarball origin URL")?,
                            unpack: true,
                        },
                        version: Some(urlpin::LockedTarballVersion { url }),
                        hashes,
                        frozen: Frozen(lon.frozen),
                    },
                    None => Pin::Url {
                        input: urlpin::UrlPin { url, unpack: true },
                        version: Some(()),
                        hashes,
                        frozen: Frozen(lon.frozen),
                    },
                }
            },
        })
    }
}

type SriHash = nix_compat::nixhash::NixHash;

/* ------------------- Upstream lon code (format v1) ---------------------- */

#[derive(Deserialize, Serialize)]
#[serde(tag = "type")]
pub enum Source {
    Git(GitSource),
    GitHub(GitHubSource),
    Tarball(TarballSource),
}

/// This type indicates what fetcher to use to download this source.
#[derive(Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum FetchType {
    Git,
    Tarball,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GitSource {
    pub fetch_type: FetchType,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub frozen: bool,

    pub branch: String,
    pub revision: String,
    pub url: String,
    pub hash: SriHash,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub last_modified: Option<u64>,
    /// Whether to fetch submodules
    #[serde(default)]
    pub submodules: bool,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GitHubSource {
    pub fetch_type: FetchType,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub frozen: bool,

    pub owner: String,
    pub repo: String,
    pub branch: String,
    pub revision: String,
    pub url: String,
    pub hash: SriHash,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TarballSource {
    pub fetch_type: FetchType,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub frozen: bool,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub origin: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub revision: Option<String>,
    pub url: String,
    pub hash: SriHash,
}
