// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Hard-coding Ethereum's chain ID makes a signature domain replayable
/// on another network that accepts the same signed bytes.
contract HardCodedEthereumDomain {
    bytes32 private constant TYPE_HASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    bytes32 private constant NAME_HASH = keccak256("Example");
    bytes32 private constant VERSION_HASH = keccak256("1");

    function domainSeparator() external view returns (bytes32) {
        return keccak256(abi.encode(TYPE_HASH, NAME_HASH, VERSION_HASH, 1, address(this)));
    }
}

/// @notice Bind the domain to the deployed chain and verifying contract.
contract ChainBoundDomain {
    bytes32 private constant TYPE_HASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    bytes32 private constant NAME_HASH = keccak256("Example");
    bytes32 private constant VERSION_HASH = keccak256("1");
    uint256 public immutable domainChainId;

    constructor() {
        domainChainId = block.chainid;
    }

    function domainSeparator() public view returns (bytes32) {
        require(block.chainid == domainChainId, "chain changed");
        return keccak256(abi.encode(TYPE_HASH, NAME_HASH, VERSION_HASH, domainChainId, address(this)));
    }

    function requireExpectedChain(uint256 expectedChainId) external view {
        require(block.chainid == expectedChainId && expectedChainId == domainChainId, "chain mismatch");
    }
}
