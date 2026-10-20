// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice A fixed address can mean a different precompile or system service
/// on another EVM. The 0x09 TRON collision is a source-backed example.
contract HardCodedBlake2Precompile {
    function run(bytes calldata input) external view returns (bytes memory output) {
        (bool ok, bytes memory result) = address(0x09).staticcall(input);
        require(ok, "precompile call failed");
        return result;
    }
}

/// @notice Bind a known-answer vector to a configured chain and address. The
/// deployment process must obtain the vector from the target chain's probe.
contract ConfiguredPrecompileVector {
    uint256 public immutable expectedChainId;
    address public immutable precompile;
    bytes32 public immutable inputHash;
    bytes32 public immutable outputHash;

    constructor(uint256 chainId_, address precompile_, bytes32 inputHash_, bytes32 outputHash_) {
        expectedChainId = chainId_;
        precompile = precompile_;
        inputHash = inputHash_;
        outputHash = outputHash_;
    }

    function runKnownVector(bytes calldata input) external view returns (bytes memory output) {
        require(block.chainid == expectedChainId, "chain mismatch");
        require(keccak256(input) == inputHash, "unexpected vector");
        (bool ok, bytes memory result) = precompile.staticcall(input);
        require(ok && keccak256(result) == outputHash, "precompile mismatch");
        return result;
    }
}
