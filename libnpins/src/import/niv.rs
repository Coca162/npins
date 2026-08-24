//! Convert+Import Niv files

use anyhow::Context;
use serde::{Deserialize, Serialize};
use std::convert::TryFrom;

use crate::{Pin, git, urlpin};

/// Pin entry from Niv's sources.json
///
/// We only take the minimum information required to get things working. This does not include
/// the actual hashes, so an update must be performed afterwards.
#[derive(Debug, Clone, Serialize, Deserialize)]
/* Counter to what one would expect from an application written in Hasekll, Niv's
 * format uses untagged data. We match it onto a Rust enum best as we can, however
 * this means that the order of the variants here is load-bearing!
 * (tbf this would probably be easier/less ambiguous if we supported all Niv fields)
 */
#[serde(untagged)]
pub enum NivPin {
    Git(NivGitPin),
    Url(NivUrlPin),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NivGitPin {
    branch: String,
    /* Either owner is None repo is the git URL, or owner is Some and then it's a GitHub owner/repo style thing */
    repo: String,
    owner: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NivUrlPin {
    r#type: String, // Should be only "tarball" or "file", but who knows
    url: String,
}

impl TryFrom<NivPin> for Pin {
    type Error = anyhow::Error;

    fn try_from(niv: NivPin) -> anyhow::Result<Self> {
        Ok(match niv {
            NivPin::Git(niv) => match niv.owner {
                None => {
                    git::GitPin::new(git::Repository::git(niv.repo.parse()?), niv.branch, false)
                        .into()
                },
                Some(owner) => git::GitPin::new(
                    git::Repository::github(&owner, &niv.repo),
                    niv.branch,
                    false,
                )
                .into(),
            },
            NivPin::Url(niv) => {
                /* In theory Niv has some support for mutability on its own, but the semantics differ
                 * to a sufficient degree that they cannot easily be mapped, and therefore the safest
                 * way is to simply import them as immutable and let the user deal with it.
                 */
                urlpin::UrlPin {
                    url: niv.url.parse().context("Invalid URL")?,
                    unpack: niv.r#type == "tarball",
                }
                .into()
            },
        })
    }
}
